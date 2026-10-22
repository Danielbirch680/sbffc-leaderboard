/*! SBFFC Leaderboard widget v2 — vanilla JS, no dependencies.
 * Usage: <div class="sbffc-lb" data-sbffc-leaderboard data-src="https://.../leaderboard.json"></div>
 * Optional data attributes:
 *   data-timezone="America/Chicago"   display zone for "last updated" (default Central, SBFFC's local time)
 *   data-refresh="300"                re-fetch interval in seconds (0 = off)
 *   data-prize-places="21"            championship places paid (draws the money line)
 *   data-view="championship"          initial view: championship|divisions|consolation|toilet|weekly
 *   data-hash="true"                  keep view/filters in the URL hash (standalone page)
 * Reads leaderboard.json schema 2.x (see SCHEMA.md); wild-card pool details need 2.1+. */
(function () {
  "use strict";
  var VIEWS = [
    ["championship", "Championship"], ["divisions", "Division Playoffs"],
    ["consolation", "Consolation"], ["toilet", "Toilet Bowl"], ["weekly", "Weekly High Scores"]
  ];
  var QUAL = {
    division_seed: ["seed", "Div seed"], fifth_team: ["fifth", "5th team"], wild_card: ["wc", "Wild card"]
  };

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  function fmt(n) { return n == null ? '<span class="pending">\u2014</span>' : Number(n).toFixed(2); }
  /* wild-card summary: top-15% pool minus teams already qualified through their division */
  function wcInfo(d) {
    var w = d.wildcards;
    if (!w) return { short: d.counts.wildcards + " wild cards", long: "", projected: false };
    var proj = w.status !== "final";
    var cut = w.cutoff_points != null ? " (cutoff " + Number(w.cutoff_points).toFixed(2) + " pts)" : "";
    var n = w.count + " wild card" + (w.count === 1 ? "" : "s");
    return {
      projected: proj,
      short: proj ? n + " projected · final count TBD" : n,
      long: "<b>Wild cards" + (proj ? " (projected)" : "") + ":</b> the top " + w.pool_size + " of " + d.counts.teams +
        " teams (" + Math.round(w.pct * 100) + "%) in total points through Week " + w.through_week + cut + " make the wild-card pool. " +
        w.pool_division_qualifiers + " of them already qualified through their division, so " +
        (proj ? "<b>" + n + " projected</b>. Final count TBD after Week " + w.final_after_week + "."
              : "<b>" + n + "</b> (final).") +
        (w.tie_resolved ? " Count includes a commissioner ruling on a points tie at the cutoff." :
          w.tie_at_cutoff ? " Points tie at the cutoff — awaiting commissioner ruling." : "")
    };
  }
  function norm(s) { return String(s || "").toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, ""); }

  function Widget(el) {
    this.el = el; el.classList.add("sbffc-lb");
    this.src = el.getAttribute("data-src") || "leaderboard.json";
    this.tz = el.getAttribute("data-timezone") || "America/Chicago";
    this.refresh = parseInt(el.getAttribute("data-refresh") || "300", 10);
    this.prize = parseInt(el.getAttribute("data-prize-places") || "21", 10);
    this.useHash = el.getAttribute("data-hash") === "true";
    this.state = { view: el.getAttribute("data-view") || "championship", q: "", div: "", qual: "", sort: {} };
    if (this.useHash) this.readHash();
    this.el.innerHTML = '<div class="lb-empty">Loading leaderboard\u2026</div>';
    this.load(true);
    var self = this;
    if (this.refresh > 0) setInterval(function () { if (!document.hidden) self.load(false); }, this.refresh * 1000);
  }

  Widget.prototype.load = function (first) {
    var self = this, url = this.src + (this.src.indexOf("?") < 0 ? "?" : "&") + "_=" + Math.floor(Date.now() / 60000);
    fetch(url, { cache: "no-store" }).then(function (r) {
      if (!r.ok) throw new Error("HTTP " + r.status); return r.json();
    }).then(function (d) {
      if (!d || !d.schema_version || String(d.schema_version).charAt(0) !== "2") throw new Error("Unsupported data format");
      self.data = d; self.render(first);
    }).catch(function (e) {
      if (first || !self.data) self.el.innerHTML = '<div class="lb-error"><b>Leaderboard temporarily unavailable.</b><br>Please check back shortly. (' + esc(e.message) + ")</div>";
    });
  };

  Widget.prototype.readHash = function () {
    var h = location.hash.replace(/^#/, ""); if (!h) return;
    var self = this;
    h.split("&").forEach(function (kv) {
      var p = kv.split("="), k = decodeURIComponent(p[0]), v = decodeURIComponent(p[1] || "");
      if (k === "view" || k === "q" || k === "div" || k === "qual") self.state[k] = v;
    });
  };
  Widget.prototype.writeHash = function () {
    if (!this.useHash) return;
    var s = this.state, parts = ["view=" + s.view];
    if (s.q) parts.push("q=" + encodeURIComponent(s.q));
    if (s.div) parts.push("div=" + encodeURIComponent(s.div));
    if (s.qual) parts.push("qual=" + s.qual);
    history.replaceState(null, "", "#" + parts.join("&"));
  };

  Widget.prototype.fmtTime = function (iso) {
    try {
      return new Intl.DateTimeFormat("en-US", { timeZone: this.tz, month: "short", day: "numeric", year: "numeric",
        hour: "numeric", minute: "2-digit", timeZoneName: "short" }).format(new Date(iso));
    } catch (e) { return iso; }
  };

  /* ---------- shell ---------- */
  Widget.prototype.render = function (first) {
    var d = this.data, s = this.state, self = this;
    var asOf = d.as_of_week, cw = d.rules.champ_weeks;
    var phase = !asOf ? "Preseason" : asOf <= d.rules.reg_end ? "Regular season" :
      asOf <= d.rules.div_playoff_weeks[1] ? "Division playoffs" : asOf < cw[cw.length - 1] ? "Championship round" : "Season complete";
    var divs = d.divisions.map(function (x) { return x.name; });
    var wci = wcInfo(d);
    var finalNote = d.final_through_week ? " Weeks 1\u2013" + d.final_through_week + " are final." : "";
    var html =
      (d.is_sample ? '<div class="lb-sample">Sample data \u2014 invented teams for preview only. Not real SBFFC results.</div>' : "") +
      '<div class="lb-head"><h2>' + esc(d.title || "SBFFC Championship") + ' <span>' + esc(d.season || "") + "</span></h2>" +
      '<div class="lb-meta"><span><span class="lb-live"></span>Last updated <b>' + esc(this.fmtTime(d.generated_at)) + "</b></span>" +
      "<span>Through <b>Week " + esc(asOf) + "</b> \u00b7 " + esc(phase) + "</span></div></div>" +
      '<div class="lb-notice">\u26A0\uFE0F ' + esc(d.status_note || "Scores are unofficial until stat corrections are final.") + esc(finalNote) + "</div>" +
      '<div class="lb-stats">' +
      '<span class="lb-stat"><b>' + d.counts.teams + "</b>teams</span>" +
      '<span class="lb-stat"><b>' + d.counts.divisions + "</b>divisions</span>" +
      '<span class="lb-stat"><b>' + d.counts.championship + "</b>in championship" + (wci.projected ? " (projected)" : "") + "</span>" +
      '<span class="lb-stat"><b>' + (d.wildcards ? d.wildcards.count : d.counts.wildcards) + "</b>" +
      (d.wildcards ? (wci.projected ? "wild cards projected · final count TBD" : "wild cards") +
        " (top-15% pool: " + d.wildcards.pool_size + ")" : "wild cards") + "</span>" +
      '<span class="lb-stat"><b>' + d.counts.consolation + "</b>consolation</span>" +
      '<span class="lb-stat"><b>' + d.counts.toilet_bowl + "</b>toilet bowl</span></div>" +
      '<div class="lb-tabs" role="tablist">' + VIEWS.map(function (v) {
        return '<button type="button" class="lb-tab" role="tab" data-view="' + v[0] + '" aria-selected="' + (s.view === v[0]) + '">' + v[1] + "</button>";
      }).join("") + "</div>" +
      '<div class="lb-controls">' +
      '<input class="lb-search" type="search" placeholder="Search team or owner" aria-label="Search team or owner" value="' + esc(s.q) + '">' +
      '<select class="lb-select lb-div" aria-label="Filter by division"><option value="">All divisions</option>' +
      divs.map(function (n) { return '<option' + (s.div === n ? " selected" : "") + ">" + esc(n) + "</option>"; }).join("") + "</select>" +
      '<select class="lb-select lb-qual" aria-label="Filter by qualifier"><option value="">All qualifiers</option>' +
      ['division_seed', 'fifth_team', 'wild_card'].map(function (k) {
        return '<option value="' + k + '"' + (s.qual === k ? " selected" : "") + ">" + QUAL[k][1] + "</option>"; }).join("") + "</select>" +
      '<span class="lb-count" aria-live="polite"></span></div>' +
      '<div class="lb-view"></div>' +
      '<div class="lb-foot">Championship total = average weekly score Weeks ' + d.rules.carry_weeks[0] + "\u2013" + d.rules.carry_weeks[1] +
      " (carry-over) + points scored Weeks " + cw[0] + "\u2013" + cw[cw.length - 1] + ". Records use SBFFC rules (Week 1 all-play, Weeks 2\u2013" +
      d.rules.reg_end + " head-to-head). Data from Sleeper; computed by SBFFC. Official results are posted by the commissioner.</div>";
    // keep focus/caret in the search box across auto-refresh
    var active = document.activeElement, hadSearch = active && active.classList && active.classList.contains("lb-search") && this.el.contains(active);
    var caret = hadSearch ? active.selectionStart : null;
    this.el.innerHTML = html;
    this.el.querySelectorAll(".lb-tab").forEach(function (b) {
      b.addEventListener("click", function () { s.view = b.getAttribute("data-view"); self.writeHash(); self.render(); });
    });
    var q = this.el.querySelector(".lb-search"), t;
    q.addEventListener("input", function () { clearTimeout(t); t = setTimeout(function () { s.q = q.value; self.writeHash(); self.renderView(); }, 120); });
    this.el.querySelector(".lb-div").addEventListener("change", function (e) { s.div = e.target.value; self.writeHash(); self.renderView(); });
    this.el.querySelector(".lb-qual").addEventListener("change", function (e) { s.qual = e.target.value; self.writeHash(); self.renderView(); });
    if (hadSearch) { q.focus(); try { q.setSelectionRange(caret, caret); } catch (e) {} }
    this.renderView();
  };

  Widget.prototype.match = function (key) {
    var t = this.data.teams[key], s = this.state;
    if (!t) return false;
    if (s.div && t.division !== s.div) return false;
    if (s.q) { var q = norm(s.q); if (norm(t.team_name).indexOf(q) < 0 && norm(t.owner).indexOf(q) < 0) return false; }
    return true;
  };

  Widget.prototype.renderView = function () {
    var v = this.state.view, box = this.el.querySelector(".lb-view");
    this.el.querySelector(".lb-qual").style.display = v === "championship" ? "" : "none";
    var out = v === "divisions" ? this.viewDivisions() : v === "consolation" ? this.viewBracket("consolation") :
      v === "toilet" ? this.viewBracket("toilet_bowl") : v === "weekly" ? this.viewWeekly() : this.viewChampionship();
    box.innerHTML = out.html;
    this.el.querySelector(".lb-count").textContent = out.count;
    this.bindSort(box);
  };

  /* ---------- generic sortable table ---------- */
  // cols: [{k, label, cls, num, sort:fn(row)->value, cell:fn(row)->html, nosort}]
  Widget.prototype.table = function (id, cols, rows, defSort, rowCls) {
    var st = this.state.sort[id] || defSort, col = cols.filter(function (c) { return c.k === st.k; })[0] || cols[0];
    var dir = st.dir === "desc" ? -1 : 1;
    rows = rows.slice().sort(function (a, b) {
      var x = col.sort(a), y = col.sort(b);
      if (x == null && y == null) return 0; if (x == null) return 1; if (y == null) return -1;
      if (typeof x === "string") return dir * x.localeCompare(y);
      return dir * (x - y);
    });
    var th = cols.map(function (c) {
      var aria = c.k === col.k ? (dir === 1 ? "ascending" : "descending") : "none";
      var inner = c.nosort ? '<span class="lb-th">' + c.label + "</span>"
        : '<button type="button" class="lb-sort" data-table="' + id + '" data-k="' + c.k + '">' + c.label + "</button>";
      return '<th scope="col" class="' + (c.cls || "") + (c.num ? " num" : "") + '"' + (c.nosort ? "" : ' aria-sort="' + aria + '"') + ">" + inner + "</th>";
    }).join("");
    var body = rows.map(function (r) {
      return '<tr class="' + (rowCls ? rowCls(r) : "") + '">' + cols.map(function (c) {
        return '<td class="' + (c.cls || "") + (c.num ? " num" : "") + '">' + c.cell(r) + "</td>";
      }).join("") + "</tr>";
    }).join("");
    if (!rows.length) body = '<tr><td colspan="' + cols.length + '" class="lb-empty">No teams match your filters.</td></tr>';
    return '<div class="lb-scroll"><table><thead><tr>' + th + "</tr></thead><tbody>" + body + "</tbody></table></div>";
  };
  Widget.prototype.bindSort = function (box) {
    var self = this;
    box.querySelectorAll(".lb-sort").forEach(function (b) {
      b.addEventListener("click", function () {
        var id = b.getAttribute("data-table"), k = b.getAttribute("data-k"), cur = self.state.sort[id];
        var numeric = b.parentNode.classList.contains("num");
        var dir = cur && cur.k === k ? (cur.dir === "asc" ? "desc" : "asc") : (numeric && k !== "rank" ? "desc" : "asc");
        self.state.sort[id] = { k: k, dir: dir }; self.renderView();
        var nb = self.el.querySelector('.lb-sort[data-table="' + id + '"][data-k="' + k + '"]'); if (nb) nb.focus();
      });
    });
  };

  Widget.prototype.teamCell = function (key, extra) {
    var t = this.data.teams[key];
    return '<div class="team"><b title="' + esc(t.team_name) + '">' + esc(t.team_name) + "</b><small>" + esc(t.owner) + '<span class="dv"> \u00b7 ' + esc(t.division) + "</span>" +
      "</small>" + (extra || "") + "</div>";
  };
  Widget.prototype.badge = function (r) {
    var q = QUAL[r.qual_type]; if (!q) return "";
    var t = this.data.teams[r.team_key];
    var label = r.qual_type === "division_seed" && t.seed ? "Seed " + t.seed : q[1];
    var proj = r.qual_type === "wild_card" && r.qual_status === "projected";
    return '<span class="badge ' + q[0] + '"' + (proj ? ' title="Projected until the regular season is final"' : "") + ">" + label + (proj ? " (proj.)" : "") + "</span>";
  };
  function mv(m) {
    if (m == null) return '<span class="mv same">\u2014</span>';
    if (m > 0) return '<span class="mv up" title="Up ' + m + '">\u25B2' + m + "</span>";
    if (m < 0) return '<span class="mv down" title="Down ' + (-m) + '">\u25BC' + (-m) + "</span>";
    return '<span class="mv same" title="No change">\u2013</span>';
  }

  /* ---------- views ---------- */
  Widget.prototype.viewChampionship = function () {
    var d = this.data, self = this, T = d.teams, s = this.state, asOf = d.as_of_week;
    var rows = d.championship.standings.filter(function (r) { return self.match(r.team_key) && (!s.qual || r.qual_type === s.qual); });
    var cur = Math.min.apply(null, d.championship.weeks.filter(function (w) { return w >= asOf; }).concat([999]));
    var cols = [
      { k: "rank", label: "#", cls: "rank sticky-1", sort: function (r) { return r.rank; },
        cell: function (r) { return r.rank + mv(r.movement); } },
      { k: "mv", label: "\u00b1", cls: "col-mv", num: true, sort: function (r) { return r.movement; }, cell: function (r) { return mv(r.movement); } },
      { k: "team", label: "Team", cls: "sticky-2", sort: function (r) { return T[r.team_key].team_name; },
        cell: function (r) { return self.teamCell(r.team_key, " " + self.badge(r) + (T[r.team_key].notes.length ? ' <span class="lb-note" title="' + esc(T[r.team_key].notes.join("; ")) + '">\u24D8</span>' : "")); } },
      { k: "owner", label: "Owner", cls: "col-owner", sort: function (r) { return T[r.team_key].owner; }, cell: function (r) { return esc(T[r.team_key].owner); } },
      { k: "div", label: "Division", cls: "col-div", sort: function (r) { return T[r.team_key].division; }, cell: function (r) { return esc(T[r.team_key].division); } },
      { k: "carry", label: '<span class="lbl-long">Carry-over</span><span class="lbl-short">Carry</span>', num: true, sort: function (r) { return r.carry_avg; }, cell: function (r) { return fmt(r.carry_avg); } }
    ];
    d.championship.weeks.forEach(function (w) {
      cols.push({ k: "w" + w, label: "Wk " + w, num: true, cls: w === asOf || (w === cur && asOf < w) ? "col-cur" : "",
        sort: function (r) { return r.weeks[String(w)]; }, cell: function (r) { return fmt(r.weeks[String(w)]); } });
    });
    cols.push({ k: "total", label: "Total", num: true, cls: "total sticky-r", sort: function (r) { return r.total; }, cell: function (r) { return fmt(r.total); } });
    var prize = this.prize;
    var wci = wcInfo(d);
    var html = (wci.long ? '<p class="lb-legend lb-wcinfo" style="padding-top:0;padding-bottom:10px"><span>' + wci.long + "</span></p>" : "") +
      this.table("champ", cols, rows, { k: "rank", dir: "asc" }, function (r) {
      return (r.rank === 1 ? "top1 " : "") + (r.rank <= prize ? "money " : "") + (r.rank === prize ? "cutline" : "");
    });
    html += '<div class="lb-legend"><span><i style="background:#c00202"></i>Top ' + prize + ' paid places</span>' +
      '<span><span class="badge seed">Seed</span> division playoff team</span><span><span class="badge fifth">5th team</span> tied best division record</span>' +
      '<span><span class="badge wc">Wild card</span> top 15% in points, not a division qualifier</span><span>\u25B2\u25BC change since previous week</span></div>';
    return { html: html, count: rows.length + " of " + d.championship.standings.length + " teams" };
  };

  Widget.prototype.viewBracket = function (kind) {
    var d = this.data, self = this, T = d.teams, b = d[kind];
    var rows = b.standings.filter(function (r) { return self.match(r.team_key); });
    var cols = [
      { k: "rank", label: "#", cls: "rank sticky-1", sort: function (r) { return r.rank; }, cell: function (r) { return r.rank; } },
      { k: "team", label: "Team", cls: "sticky-2", sort: function (r) { return T[r.team_key].team_name; }, cell: function (r) { return self.teamCell(r.team_key); } },
      { k: "owner", label: "Owner", cls: "col-owner", sort: function (r) { return T[r.team_key].owner; }, cell: function (r) { return esc(T[r.team_key].owner); } },
      { k: "div", label: "Division", cls: "col-div", sort: function (r) { return T[r.team_key].division; }, cell: function (r) { return esc(T[r.team_key].division); } },
      { k: "rec", label: "Record", cls: "col-rec", sort: function (r) { var x = T[r.team_key].record; return x.w + x.t / 2; }, cell: function (r) { return esc(T[r.team_key].record_str); } }
    ];
    b.weeks.forEach(function (w) {
      cols.push({ k: "w" + w, label: "Wk " + w, num: true, cls: w === d.as_of_week ? "col-cur" : "", sort: function (r) { return r.weeks[String(w)]; }, cell: function (r) { return fmt(r.weeks[String(w)]); } });
    });
    cols.push({ k: "total", label: "Total", num: true, cls: "total sticky-r", sort: function (r) { return r.total; }, cell: function (r) { return fmt(r.total); } });
    var name = kind === "consolation" ? "Consolation Bracket" : "Toilet Bowl";
    var who = kind === "consolation" ? "Teams at or above .500 after Week " + d.rules.reg_end + " that did not reach the championship round."
      : "All remaining teams not eligible for the Championship or Consolation brackets.";
    var html = '<p class="lb-legend" style="padding-top:0;padding-bottom:10px"><span><b>' + name + ":</b> " + who +
      " Most total points Weeks " + b.weeks[0] + "\u2013" + b.weeks[b.weeks.length - 1] + " wins.</span></p>" +
      this.table(kind, cols, rows, { k: "rank", dir: "asc" }, function (r) { return r.rank === 1 ? "top1" : ""; });
    return { html: html, count: rows.length + " of " + b.standings.length + " teams" };
  };

  Widget.prototype.viewDivisions = function () {
    var d = this.data, self = this, T = d.teams, s = this.state;
    var list = d.divisions.filter(function (x) {
      if (s.div && x.name !== s.div) return false;
      return !s.q || x.standings.some(function (k) { return self.match(k); });
    });
    function side(g, which, win) {
      var x = g[which]; if (!x) return '<div class="side"><span class="sd"></span><span class="nm pending">TBD</span><span class="pt"></span></div>';
      var t = T[x.team_key];
      return '<div class="side' + (win === x.team_key ? " win" : "") + '"><span class="sd">' + x.seed + '</span><span class="nm" title="' + esc(t.team_name) + '">' +
        esc(t.team_name) + '</span><span class="pt">' + fmt(x.points) + "</span></div>";
    }
    function game(g, label, cls) {
      return '<div class="game ' + (cls || "") + '"><div class="gw">' + label + " \u00b7 Week " + g.week + (g.note ? " \u00b7 " + esc(g.note) : "") +
        "</div>" + side(g, "home", g.winner) + side(g, "away", g.winner) + "</div>";
    }
    var cards = list.map(function (dv) {
      var po = dv.playoffs, aw = dv.awards;
      var rows = dv.standings.map(function (k, i) {
        var t = T[k], hit = s.q && self.match(k);
        return '<tr class="' + (t.seed ? "is-seed" : "") + '"' + (hit ? ' style="outline:2px solid #ffb400;outline-offset:-2px"' : "") + "><td>" + (i + 1) + "</td><td>" + self.teamCell(k) + "</td>" +
          "<td>" + (t.seed ? '<span class="badge seed">' + t.seed + "</span>" : t.qual_type === "fifth_team" ? '<span class="badge fifth">5th</span>' : t.qual_type === "wild_card" ? '<span class="badge wc"' + (d.wildcards && d.wildcards.status !== "final" ? ' title="Projected wild card">WC?' : ">WC") + "</span>" : "") +
          '</td><td class="num">' + esc(t.record_str) + '</td><td class="num">' + fmt(t.reg_pts) + "</td></tr>";
      }).join("");
      var br = "";
      if (po) {
        br = '<div class="bracket"><h4>Division playoffs</h4>' + game(po.semifinals[0], "Semi") + game(po.semifinals[1], "Semi") +
          game(po.final, "Final", "final") +
          (po.champion ? '<div class="champline">\uD83C\uDFC6 ' + esc(T[po.champion].team_name) + "</div>" : "") + "</div>";
      }
      return '<section class="card"><div class="card-h"><h3>' + esc(dv.name) + "</h3><span>" + dv.num_teams + " teams</span></div>" +
        '<div class="awards"><span class="badge soft">Best record</span> ' + esc(T[aw.best_record].team_name) +
        ' <span class="badge soft">Most points</span> ' + esc(T[aw.most_points].team_name) + "</div>" +
        '<table><thead><tr><th><span class="lb-th">#</span></th><th><span class="lb-th">Team</span></th><th><span class="lb-th">Q</span></th><th class="num"><span class="lb-th">W-L</span></th><th class="num"><span class="lb-th">PF</span></th></tr></thead><tbody>' +
        rows + "</tbody></table>" + br + "</section>";
    }).join("");
    if (!list.length) cards = '<div class="lb-empty">No divisions match your filters.</div>';
    return { html: '<div class="lb-grid">' + cards + "</div>", count: list.length + " of " + d.divisions.length + " divisions" };
  };

  Widget.prototype.viewWeekly = function () {
    var d = this.data, self = this, T = d.teams;
    var rows = d.weekly_high.filter(function (r) { return r.team_key ? self.match(r.team_key) : !self.state.q && !self.state.div; });
    var mp = d.most_points_overall, best = null;
    d.weekly_high.forEach(function (r) { if (r.points != null && (!best || r.points > best.points)) best = r; });
    var hero = '<div class="lb-hero">' +
      (best ? '<div class="hero"><small>Highest single week (Wks 1\u2013' + d.rules.reg_end + ")</small><strong>" + fmt(best.points) + "</strong>" + esc(T[best.team_key].team_name) + " \u00b7 Week " + best.week + "</div>" : "") +
      (mp ? '<div class="hero"><small>Most total points (Wks 1\u2013' + d.rules.reg_end + ")</small><strong>" + fmt(mp.points) + "</strong>" + esc(T[mp.team_key].team_name) + " \u00b7 " + esc(T[mp.team_key].division) + "</div>" : "") +
      "</div>";
    var cols = [
      { k: "week", label: "Week", cls: "rank sticky-1", sort: function (r) { return r.week; }, cell: function (r) { return r.week; } },
      { k: "team", label: "Team", cls: "sticky-2", sort: function (r) { return r.team_key ? T[r.team_key].team_name : null; },
        cell: function (r) { return r.team_key ? self.teamCell(r.team_key, r.ties.length ? ' <span class="badge soft">tie +' + r.ties.length + "</span>" : "") : '<span class="pending">Not played yet</span>'; } },
      { k: "owner", label: "Owner", cls: "col-owner", sort: function (r) { return r.team_key ? T[r.team_key].owner : null; }, cell: function (r) { return r.team_key ? esc(T[r.team_key].owner) : ""; } },
      { k: "div", label: "Division", cls: "col-div", sort: function (r) { return r.team_key ? T[r.team_key].division : null; }, cell: function (r) { return r.team_key ? esc(T[r.team_key].division) : ""; } },
      { k: "pts", label: "Points", num: true, cls: "total", sort: function (r) { return r.points; }, cell: function (r) { return fmt(r.points); } }
    ];
    return { html: hero + this.table("weekly", cols, rows, { k: "week", dir: "asc" }), count: rows.length + " weeks" };
  };

  function init() {
    document.querySelectorAll("[data-sbffc-leaderboard]").forEach(function (el) {
      if (!el.__sbffc) { el.__sbffc = new Widget(el); }
    });
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init); else init();
  window.addEventListener("mercury:load", init); // Squarespace AJAX page loads
  window.SBFFCLeaderboard = { init: init };
})();
