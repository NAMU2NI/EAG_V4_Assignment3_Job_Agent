import json
import tempfile
from pathlib import Path

import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(
    page_title="Job Search Agent",
    page_icon="briefcase",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Styles ───────────────────────────────────────────────────────────────────
st.markdown("""
<style>
.metric-card {
    background: #1e1e2e;
    border-radius: 12px;
    padding: 18px 20px;
    border-left: 4px solid #7c3aed;
    margin-bottom: 10px;
}
.metric-label { color: #a0a0b0; font-size: 12px; text-transform: uppercase; letter-spacing: 1px; }
.metric-value { color: #ffffff; font-size: 22px; font-weight: 700; margin-top: 4px; }
.tag {
    display: inline-block;
    background: #2d2d44;
    color: #c4b5fd;
    border-radius: 20px;
    padding: 3px 12px;
    font-size: 12px;
    margin: 3px 2px;
}
.tag-green { background: #14532d; color: #86efac; }
.tag-blue  { background: #1e3a5f; color: #93c5fd; }
.tag-red   { background: #450a0a; color: #fca5a5; }
.signal-badge {
    display: inline-block;
    padding: 2px 10px;
    border-radius: 20px;
    font-size: 11px;
    font-weight: 600;
}
.job-card {
    background: #1a1a2e;
    border-radius: 10px;
    padding: 14px 18px;
    margin-bottom: 8px;
    border-left: 4px solid #7c3aed;
}
.section-title { color: #a78bfa; font-size: 13px; font-weight: 600; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 8px; }
</style>
""", unsafe_allow_html=True)


# ── Session State ─────────────────────────────────────────────────────────────
for key in ["profile", "leads", "scored_jobs", "digest"]:
    if key not in st.session_state:
        st.session_state[key] = None


# ── Helper renderers ──────────────────────────────────────────────────────────
def tags_html(items: list[str], style: str = "") -> str:
    cls = f"tag {style}".strip()
    return " ".join(f'<span class="{cls}">{i}</span>' for i in items if i)


def score_color(score: int) -> str:
    if score >= 8: return "#22c55e"
    if score >= 6: return "#facc15"
    return "#f87171"


def fit_badge(rec: str) -> str:
    colors = {
        "strong fit": ("#14532d", "#86efac"),
        "good fit":   ("#1e3a5f", "#93c5fd"),
        "partial fit":("#713f12", "#fde68a"),
        "skip":       ("#450a0a", "#fca5a5"),
    }
    bg, fg = colors.get(rec, ("#2d2d44", "#e2e8f0"))
    return f'<span style="background:{bg};color:{fg};padding:2px 10px;border-radius:20px;font-size:11px;font-weight:600;">{rec}</span>'


# ── Header ────────────────────────────────────────────────────────────────────
st.markdown("## Job Search Agent")
st.markdown("Scrape news signals · Match jobs · Get your daily digest")
st.divider()

tab1, tab2, tab3, tab4 = st.tabs(["Resume Parser", "Job Market Signals", "Top Job Matches", "Resume Tweaker"])


# ═══════════════════════════════════════════════════════════
# TAB 1 — RESUME PARSER
# ═══════════════════════════════════════════════════════════
with tab1:
    st.markdown("### Upload Your Resume")
    col_upload, col_gap = st.columns([2, 3])

    with col_upload:
        uploaded = st.file_uploader("PDF or DOCX", type=["pdf", "docx", "txt"], label_visibility="collapsed")
        parse_btn = st.button("Parse Resume", type="primary", disabled=uploaded is None)

    if parse_btn and uploaded:
        suffix = Path(uploaded.name).suffix
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(uploaded.read())
            tmp_path = tmp.name

        with st.spinner("Parsing with GPT-4o..."):
            from resume_parser import ResumeParser
            parser = ResumeParser()
            profile = parser.parse(tmp_path)
            st.session_state.profile = profile
            Path("profile.json").write_text(json.dumps(profile.model_dump(), indent=2))

        st.success("Resume parsed successfully!")

    profile = st.session_state.profile
    if profile is None and Path("profile.json").exists():
        from resume_parser.models import ResumeProfile
        profile = ResumeProfile(**json.loads(Path("profile.json").read_text()))
        st.session_state.profile = profile

    if profile:
        st.divider()

        # ── Top metrics ───────────────────────────────────────────────────────
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Name", profile.name)
        m2.metric("Experience", f"{profile.total_experience_years} yrs")
        m3.metric("Seniority", profile.seniority_level.title())
        m4.metric("Current Role", profile.current_role)

        st.markdown("")

        left, right = st.columns(2)

        with left:
            # Target roles
            st.markdown('<p class="section-title">Target Roles</p>', unsafe_allow_html=True)
            st.markdown(tags_html(profile.target_roles, "tag-blue"), unsafe_allow_html=True)

            st.markdown("<br>", unsafe_allow_html=True)

            # Technical skills
            st.markdown('<p class="section-title">Technical Skills</p>', unsafe_allow_html=True)
            st.markdown(tags_html(profile.technical_skills), unsafe_allow_html=True)

            st.markdown("<br>", unsafe_allow_html=True)

            # Tools
            st.markdown('<p class="section-title">Tools & Platforms</p>', unsafe_allow_html=True)
            st.markdown(tags_html(profile.tools, "tag-green"), unsafe_allow_html=True)

        with right:
            # Skills radar / bar chart
            all_skills = profile.technical_skills[:12] + profile.domain_skills[:5]
            if all_skills:
                # Simple horizontal bar as a "skill presence" chart
                fig = go.Figure(go.Bar(
                    y=all_skills[:15],
                    x=[1] * len(all_skills[:15]),
                    orientation="h",
                    marker=dict(
                        color=["#7c3aed"] * len(profile.technical_skills[:12]) +
                              ["#2563eb"] * len(profile.domain_skills[:5]),
                        line=dict(color="#0f0f1a", width=1),
                    ),
                    text=all_skills[:15],
                    textposition="inside",
                    insidetextanchor="start",
                    textfont=dict(color="white", size=12),
                ))
                fig.update_layout(
                    title="Skills Profile",
                    height=380,
                    margin=dict(l=10, r=10, t=40, b=10),
                    paper_bgcolor="#0f0f1a",
                    plot_bgcolor="#0f0f1a",
                    xaxis=dict(visible=False),
                    yaxis=dict(visible=False, autorange="reversed"),
                    showlegend=False,
                )
                st.plotly_chart(fig, use_container_width=True)

        st.divider()

        # ── Work Experience ───────────────────────────────────────────────────
        st.markdown('<p class="section-title">Work Experience</p>', unsafe_allow_html=True)
        for exp in profile.work_experience:
            with st.expander(f"{exp.role} — {exp.company}  ({exp.duration_years or '?'} yrs)"):
                st.write(exp.description)

        st.markdown("")
        st.markdown('<p class="section-title">Summary</p>', unsafe_allow_html=True)
        st.info(profile.summary)


# ═══════════════════════════════════════════════════════════
# TAB 2 — JOB MARKET SIGNALS
# ═══════════════════════════════════════════════════════════
with tab2:
    st.markdown("### Job Market Signals from News")
    st.caption("Scrapes Google News, YourStory, Inc42 for funding & GCC expansion announcements")

    run_news = st.button("Fetch Latest News Signals", type="primary")

    if run_news:
        with st.spinner("Scanning Google News, YourStory, Inc42..."):
            from news_scraper import NewsScraper
            scraper = NewsScraper()
            leads = scraper.run(save_path="company_leads.json")
            st.session_state.leads = leads
        st.success(f"Done — {len(leads)} company signals extracted")

    leads = st.session_state.leads
    if leads is None and Path("company_leads.json").exists():
        from news_scraper.models import CompanyLead
        leads = [CompanyLead(**l) for l in json.loads(Path("company_leads.json").read_text())]
        st.session_state.leads = leads

    # Load raw news items for the feed section
    news_items_raw = []
    if Path("news_items.json").exists():
        from news_scraper.models import NewsItem
        news_items_raw = [NewsItem(**n) for n in json.loads(Path("news_items.json").read_text())]

    if leads:
        from collections import Counter

        # ── Top metrics row ───────────────────────────────────────────────────
        total_articles = len(news_items_raw)
        sig_counts = Counter(l.signal for l in leads)
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Articles Scanned", total_articles)
        m2.metric("Company Leads", len(leads))
        m3.metric("Funding Signals", sig_counts.get("funding", 0))
        m4.metric("GCC Expansions", sig_counts.get("gcc_expansion", 0))

        st.divider()

        signal_colors = {
            "funding":       ("#1e3a5f", "#93c5fd"),
            "gcc_expansion": ("#14532d", "#86efac"),
            "hiring":        ("#713f12", "#fde68a"),
        }

        left_col, right_col = st.columns([3, 2])

        # ── Left: Detailed company cards ──────────────────────────────────────
        with left_col:
            st.markdown('<p class="section-title">Company Signals with Sources</p>', unsafe_allow_html=True)

            for lead in leads:
                bg, fg = signal_colors.get(lead.signal, ("#2d2d44", "#e2e8f0"))
                badge = f'<span style="background:{bg};color:{fg};padding:2px 10px;border-radius:20px;font-size:11px;font-weight:600;">{lead.signal.replace("_", " ").title()}</span>'
                sc = score_color(lead.relevance_score)

                # Build article links HTML
                article_links_html = ""
                if lead.source_articles:
                    links = []
                    for art in lead.source_articles[:4]:
                        if art.url and art.title:
                            title_short = art.title[:80] + ("..." if len(art.title) > 80 else "")
                            src_label = f" &middot; {art.source}" if art.source else ""
                            pub_label = f" &middot; {art.published[:16]}" if art.published else ""
                            links.append(
                                f'<div style="margin:4px 0;">'
                                f'<a href="{art.url}" target="_blank" style="color:#818cf8;font-size:12px;text-decoration:none;">'
                                f'&#128279; {title_short}</a>'
                                f'<span style="color:#4b5563;font-size:11px;">{src_label}{pub_label}</span>'
                                f'{"<div style=\'color:#6b7280;font-size:11px;margin-left:18px;\'>" + art.snippet[:120] + "...</div>" if art.snippet else ""}'
                                f'</div>'
                            )
                        elif art.url:
                            links.append(
                                f'<div style="margin:4px 0;">'
                                f'<a href="{art.url}" target="_blank" style="color:#818cf8;font-size:12px;">&#128279; Source article</a>'
                                f'</div>'
                            )
                    article_links_html = "".join(links)

                expander_label = f"{lead.company_name}  —  {lead.signal.replace('_', ' ').title()}  |  Score {lead.relevance_score}/10"
                with st.expander(expander_label, expanded=(lead.relevance_score >= 8)):
                    st.markdown(f"""
                    <div style="margin-bottom:10px;">
                      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
                        <div>{badge} &nbsp; <span style="color:#d1d5db;font-size:13px;">{lead.domain}</span></div>
                        <span style="color:{sc};font-size:20px;font-weight:800;">{lead.relevance_score}/10</span>
                      </div>
                      <div style="color:#e2e8f0;font-size:14px;margin-bottom:10px;">
                        <strong>What happened:</strong> {lead.signal_detail}
                      </div>
                      <div style="color:#9ca3af;font-size:12px;">
                        <strong style="color:#6b7280;text-transform:uppercase;letter-spacing:1px;font-size:11px;">Location:</strong>
                        {lead.location}
                      </div>
                    </div>
                    """, unsafe_allow_html=True)

                    if article_links_html:
                        st.markdown(
                            f'<div style="border-top:1px solid #374151;margin-top:8px;padding-top:8px;">'
                            f'<p style="color:#6b7280;font-size:11px;text-transform:uppercase;letter-spacing:1px;margin-bottom:6px;">Source Articles</p>'
                            f'{article_links_html}</div>',
                            unsafe_allow_html=True
                        )
                    else:
                        st.caption("No direct source articles found for this company.")

        # ── Right: Charts ─────────────────────────────────────────────────────
        with right_col:
            # Signal type donut
            fig_donut = go.Figure(go.Pie(
                labels=[k.replace("_", " ").title() for k in sig_counts.keys()],
                values=list(sig_counts.values()),
                hole=0.55,
                marker=dict(colors=["#7c3aed", "#2563eb", "#0891b2"]),
                textinfo="label+percent",
                textfont=dict(color="white", size=12),
            ))
            fig_donut.update_layout(
                title="Signal Breakdown",
                height=240,
                margin=dict(l=10, r=10, t=40, b=10),
                paper_bgcolor="#0f0f1a",
                plot_bgcolor="#0f0f1a",
                showlegend=False,
            )
            st.plotly_chart(fig_donut, use_container_width=True)

            # Relevance scores — horizontal bar
            sorted_leads = sorted(leads, key=lambda x: x.relevance_score)
            fig_bar = go.Figure(go.Bar(
                y=[l.company_name[:20] for l in sorted_leads],
                x=[l.relevance_score for l in sorted_leads],
                orientation="h",
                marker=dict(color=[score_color(l.relevance_score) for l in sorted_leads]),
                text=[l.relevance_score for l in sorted_leads],
                textposition="outside",
                textfont=dict(color="white", size=11),
                customdata=[l.signal.replace("_", " ") for l in sorted_leads],
                hovertemplate="<b>%{y}</b><br>Score: %{x}<br>Signal: %{customdata}<extra></extra>",
            ))
            fig_bar.update_layout(
                title="Relevance Scores",
                height=350,
                margin=dict(l=10, r=40, t=40, b=10),
                paper_bgcolor="#0f0f1a",
                plot_bgcolor="#0f0f1a",
                xaxis=dict(range=[0, 11], color="#6b7280", showgrid=False),
                yaxis=dict(color="#9ca3af"),
                font=dict(color="#9ca3af"),
            )
            st.plotly_chart(fig_bar, use_container_width=True)

        # ── Raw News Feed ──────────────────────────────────────────────────────
        if news_items_raw:
            st.divider()
            st.markdown('<p class="section-title">Raw News Feed — All Scanned Articles</p>', unsafe_allow_html=True)
            search_term = st.text_input("Filter articles", placeholder="e.g. GCC, funding, Bangalore...", label_visibility="collapsed")

            filtered_news = [
                n for n in news_items_raw
                if not search_term or search_term.lower() in (n.title + n.summary).lower()
            ]
            st.caption(f"Showing {len(filtered_news)} of {len(news_items_raw)} articles")

            for item in filtered_news[:40]:
                pub = f" &middot; {item.published[:16]}" if item.published else ""
                snippet = item.summary[:160] + "..." if len(item.summary) > 160 else item.summary
                st.markdown(
                    f'<div style="padding:8px 0;border-bottom:1px solid #1f2937;">'
                    f'<a href="{item.url}" target="_blank" style="color:#c4b5fd;font-size:13px;font-weight:500;text-decoration:none;">'
                    f'{item.title}</a>'
                    f'<span style="color:#4b5563;font-size:11px;"> &middot; {item.source}{pub}</span>'
                    f'{"<div style=\'color:#6b7280;font-size:12px;margin-top:3px;\'>" + snippet + "</div>" if snippet else ""}'
                    f'</div>',
                    unsafe_allow_html=True
                )


# ═══════════════════════════════════════════════════════════
# TAB 3 — TOP JOB MATCHES
# ═══════════════════════════════════════════════════════════
with tab3:
    st.markdown("### Top Job Matches")

    if st.session_state.profile is None and not Path("profile.json").exists():
        st.warning("Parse your resume first (Tab 1)")
    elif st.session_state.leads is None and not Path("company_leads.json").exists():
        st.warning("Fetch news signals first (Tab 2)")
    else:
        col_run, col_n, col_fit = st.columns([2, 2, 3])

        with col_run:
            run_filter = st.button("Search & Score Jobs", type="primary")
        with col_n:
            top_n = st.slider("Top N results", min_value=5, max_value=50, value=15, step=5)
        with col_fit:
            fit_filter = st.multiselect(
                "Filter by fit",
                ["strong fit", "good fit", "partial fit"],
                default=["strong fit", "good fit"],
            )

        if run_filter:
            from resume_parser.models import ResumeProfile
            from news_scraper.models import CompanyLead
            from job_filter import JobFilter

            profile = ResumeProfile(**json.loads(Path("profile.json").read_text()))
            leads = [CompanyLead(**l) for l in json.loads(Path("company_leads.json").read_text())]

            with st.spinner("Searching jobs on LinkedIn..."):
                jf = JobFilter()
                scored = jf.run(profile, leads, save_path="scored_jobs.json")
                st.session_state.scored_jobs = scored

        scored_jobs = st.session_state.scored_jobs
        if scored_jobs is None and Path("scored_jobs.json").exists():
            from job_filter.models import ScoredJob
            scored_jobs = [ScoredJob(**s) for s in json.loads(Path("scored_jobs.json").read_text())]
            st.session_state.scored_jobs = scored_jobs

        if scored_jobs:
            # Apply filters
            filtered = [s for s in scored_jobs if s.recommendation in fit_filter][:top_n]
            st.caption(f"Showing {len(filtered)} of {len(scored_jobs)} matched jobs")
            st.divider()

            left_col, right_col = st.columns([3, 2])

            with left_col:
                st.markdown('<p class="section-title">Job Cards</p>', unsafe_allow_html=True)
                for i, sj in enumerate(filtered, 1):
                    sc = score_color(sj.match_score)
                    badge = fit_badge(sj.recommendation)
                    matched = tags_html(sj.matched_skills[:5], "tag-green")
                    missing = tags_html(sj.missing_skills[:3], "tag-red")
                    st.markdown(f"""
                    <div class="job-card" style="border-left-color:{sc};">
                      <div style="display:flex;justify-content:space-between;align-items:flex-start;">
                        <div>
                          <span style="color:#e2e8f0;font-size:15px;font-weight:600;">#{i} {sj.job.title}</span><br>
                          <span style="color:#9ca3af;font-size:13px;">{sj.job.company} &middot; {sj.job.location}</span>
                        </div>
                        <div style="text-align:right;">
                          <span style="color:{sc};font-size:20px;font-weight:800;">{sj.match_score}/10</span><br>
                          {badge}
                        </div>
                      </div>
                      <div style="margin-top:6px;display:flex;gap:8px;align-items:center;">
                        {"<span style='background:#1e3a5f;color:#93c5fd;padding:1px 8px;border-radius:20px;font-size:11px;font-weight:600;'>LinkedIn</span>" if sj.job.source == "linkedin" else "<span style='background:#4a1d96;color:#ddd6fe;padding:1px 8px;border-radius:20px;font-size:11px;font-weight:600;'>Naukri</span>"}
                        {"<span style='color:#6b7280;font-size:11px;'>" + sj.job.posted_date[:10] + "</span>" if sj.job.posted_date else ""}
                        {"<span style='color:#6b7280;font-size:11px;'>" + sj.job.experience_required + "</span>" if sj.job.experience_required else ""}
                      </div>
                      <div style="margin-top:8px;display:flex;gap:16px;">
                        <span style="color:#a78bfa;font-size:12px;">Domain <strong style="color:{score_color(sj.domain_score)}">{sj.domain_score}/10</strong></span>
                        <span style="color:#a78bfa;font-size:12px;">Industry <strong style="color:{score_color(sj.industry_score)}">{sj.industry_score}/10</strong></span>
                        <span style="color:#a78bfa;font-size:12px;">Skills <strong style="color:{score_color(sj.skill_score)}">{sj.skill_score}/10</strong></span>
                        <span style="color:#a78bfa;font-size:12px;">Seniority <strong style="color:{score_color(sj.seniority_score)}">{sj.seniority_score}/10</strong></span>
                      </div>
                      <div style="margin-top:6px;color:#9ca3af;font-size:12px;">{sj.gpt_reasoning[:150]}</div>
                      <div style="margin-top:6px;">{matched}</div>
                      {"<div style='margin-top:4px;color:#6b7280;font-size:12px;'>Domains: " + ", ".join(sj.matched_domains[:3]) + "</div>" if sj.matched_domains else ""}
                      {"<div style='margin-top:2px;color:#6b7280;font-size:12px;'>Industries: " + ", ".join(sj.matched_industries[:3]) + "</div>" if sj.matched_industries else ""}
                      {"<div style='margin-top:4px;'>Missing: " + missing + "</div>" if sj.missing_skills else ""}
                      <div style="margin-top:8px;"><a href="{sj.job.url}" target="_blank" style="color:#7c3aed;font-size:12px;">View on {sj.job.source.title()}</a></div>
                    </div>
                    """, unsafe_allow_html=True)

            with right_col:
                # Score distribution
                all_scores = [s.match_score for s in scored_jobs]
                fig_hist = px.histogram(
                    x=all_scores, nbins=10,
                    labels={"x": "Match Score", "y": "Count"},
                    title="Score Distribution",
                    color_discrete_sequence=["#7c3aed"],
                )
                fig_hist.update_layout(
                    height=230,
                    margin=dict(l=10, r=10, t=40, b=10),
                    paper_bgcolor="#0f0f1a",
                    plot_bgcolor="#0f0f1a",
                    font=dict(color="#9ca3af"),
                    bargap=0.1,
                )
                st.plotly_chart(fig_hist, use_container_width=True)

                # Source breakdown (LinkedIn vs Naukri)
                from collections import Counter
                src_counts = Counter(s.job.source for s in scored_jobs)
                fig_src = go.Figure(go.Pie(
                    labels=list(src_counts.keys()),
                    values=list(src_counts.values()),
                    hole=0.5,
                    marker=dict(colors=["#2563eb", "#7c3aed"]),
                    textinfo="label+value",
                    textfont=dict(color="white", size=12),
                ))
                fig_src.update_layout(
                    title="Jobs by Source",
                    height=200,
                    margin=dict(l=10, r=10, t=40, b=10),
                    paper_bgcolor="#0f0f1a",
                    showlegend=False,
                )
                st.plotly_chart(fig_src, use_container_width=True)

                # Fit category breakdown
                rec_counts = Counter(s.recommendation for s in scored_jobs)
                order = ["strong fit", "good fit", "partial fit", "skip"]
                clrs = ["#22c55e", "#3b82f6", "#facc15", "#f87171"]
                labels = [r for r in order if r in rec_counts]
                values = [rec_counts[r] for r in labels]
                bar_colors = [clrs[order.index(r)] for r in labels]

                fig_fit = go.Figure(go.Bar(
                    x=labels, y=values,
                    marker=dict(color=bar_colors),
                    text=values, textposition="outside",
                    textfont=dict(color="white"),
                ))
                fig_fit.update_layout(
                    title="Fit Breakdown",
                    height=230,
                    margin=dict(l=10, r=10, t=40, b=30),
                    paper_bgcolor="#0f0f1a",
                    plot_bgcolor="#0f0f1a",
                    font=dict(color="#9ca3af"),
                    xaxis=dict(color="#6b7280"),
                    yaxis=dict(color="#6b7280"),
                    showlegend=False,
                )
                st.plotly_chart(fig_fit, use_container_width=True)

                # Top companies
                from collections import Counter as C2
                company_counts = C2(s.job.company for s in scored_jobs if s.recommendation in ["strong fit", "good fit"])
                top_cos = company_counts.most_common(8)
                if top_cos:
                    fig_co = go.Figure(go.Bar(
                        y=[c[0][:20] for c in top_cos],
                        x=[c[1] for c in top_cos],
                        orientation="h",
                        marker=dict(color="#7c3aed"),
                        text=[c[1] for c in top_cos],
                        textposition="outside",
                        textfont=dict(color="white"),
                    ))
                    fig_co.update_layout(
                        title="Top Companies",
                        height=280,
                        margin=dict(l=10, r=30, t=40, b=10),
                        paper_bgcolor="#0f0f1a",
                        plot_bgcolor="#0f0f1a",
                        font=dict(color="#9ca3af"),
                        xaxis=dict(color="#6b7280"),
                        yaxis=dict(color="#9ca3af", autorange="reversed"),
                    )
                    st.plotly_chart(fig_co, use_container_width=True)


# ═══════════════════════════════════════════════════════════
# TAB 4 — RESUME TWEAKER
# ═══════════════════════════════════════════════════════════
with tab4:
    st.markdown("### Resume Tweaker")
    st.caption("Pick a job from your matches — get targeted, minimal tweaks to your resume for that specific JD.")

    profile = st.session_state.profile
    if profile is None and Path("profile.json").exists():
        from resume_parser.models import ResumeProfile
        profile = ResumeProfile(**json.loads(Path("profile.json").read_text()))
        st.session_state.profile = profile

    scored_jobs = st.session_state.scored_jobs
    if scored_jobs is None and Path("scored_jobs.json").exists():
        from job_filter.models import ScoredJob
        scored_jobs = [ScoredJob(**s) for s in json.loads(Path("scored_jobs.json").read_text())]
        st.session_state.scored_jobs = scored_jobs

    if not profile:
        st.warning("Parse your resume first in Tab 1.")
    elif not scored_jobs:
        st.warning("Run job search in Tab 3 first.")
    else:
        # ── Job selector ─────────────────────────────────────────────────────
        good_jobs = [s for s in scored_jobs if s.recommendation in ("strong fit", "good fit")][:20]
        job_labels = [
            f"{sj.job.title} @ {sj.job.company}  [{sj.job.source.upper()}]  — {sj.match_score}/10  (D:{sj.domain_score} I:{sj.industry_score})"
            for sj in good_jobs
        ]

        col_sel, col_btn = st.columns([4, 1])
        with col_sel:
            selected_label = st.selectbox("Select a job to tailor your resume for", job_labels, label_visibility="collapsed")
        with col_btn:
            tweak_btn = st.button("Tweak My Resume", type="primary")

        selected_idx = job_labels.index(selected_label)
        selected_sj = good_jobs[selected_idx]

        # ── Show selected job summary ─────────────────────────────────────────
        sc = score_color(selected_sj.match_score)
        st.markdown(f"""
        <div class="job-card" style="border-left-color:{sc};margin-bottom:16px;">
          <div style="display:flex;justify-content:space-between;">
            <div>
              <strong style="color:#e2e8f0;font-size:15px;">{selected_sj.job.title}</strong>
              &nbsp;&nbsp;<span style="color:#9ca3af;font-size:13px;">{selected_sj.job.company} &middot; {selected_sj.job.location}</span>
            </div>
            <span style="color:{sc};font-size:18px;font-weight:800;">{selected_sj.match_score}/10</span>
          </div>
          <div style="margin-top:6px;display:flex;gap:16px;">
            <span style="color:#a78bfa;font-size:12px;">Domain <strong style="color:{score_color(selected_sj.domain_score)}">{selected_sj.domain_score}/10</strong></span>
            <span style="color:#a78bfa;font-size:12px;">Industry <strong style="color:{score_color(selected_sj.industry_score)}">{selected_sj.industry_score}/10</strong></span>
            <span style="color:#a78bfa;font-size:12px;">Skills <strong style="color:{score_color(selected_sj.skill_score)}">{selected_sj.skill_score}/10</strong></span>
          </div>
          <div style="margin-top:6px;color:#9ca3af;font-size:12px;">{selected_sj.gpt_reasoning}</div>
          <div style="margin-top:6px;"><a href="{selected_sj.job.url}" target="_blank" style="color:#7c3aed;font-size:12px;">View Job</a></div>
        </div>
        """, unsafe_allow_html=True)

        if tweak_btn:
            with st.spinner(f"Fetching full JD for {selected_sj.job.title} @ {selected_sj.job.company}..."):
                from job_filter.searcher import fetch_jd_for_job
                jd_text = fetch_jd_for_job(selected_sj.job)
                if jd_text:
                    selected_sj.job.description = jd_text
                    with st.expander("Job Description fetched", expanded=False):
                        st.text(jd_text[:2000])
                else:
                    jd_text = selected_sj.job.title
                    st.info("Could not fetch JD — tweaking based on job title only.")

            with st.spinner(f"Generating resume tweaks..."):
                from resume_tweaker import ResumeTweaker
                tweaker = ResumeTweaker()
                result = tweaker.tweak(
                    profile=profile,
                    job_title=selected_sj.job.title,
                    company=selected_sj.job.company,
                    jd_text=jd_text,
                )
                st.session_state["tweak_result"] = result

        result = st.session_state.get("tweak_result")
        if result and result.job_title in selected_label:
            st.divider()

            # ── Alignment banner ──────────────────────────────────────────────
            a1, a2 = st.columns(2)
            with a1:
                st.markdown(f"""
                <div class="metric-card">
                  <div class="metric-label">Domain Alignment</div>
                  <div style="color:#c4b5fd;font-size:13px;margin-top:6px;">{result.domain_alignment}</div>
                </div>""", unsafe_allow_html=True)
            with a2:
                st.markdown(f"""
                <div class="metric-card">
                  <div class="metric-label">Industry Alignment</div>
                  <div style="color:#86efac;font-size:13px;margin-top:6px;">{result.industry_alignment}</div>
                </div>""", unsafe_allow_html=True)

            st.markdown(f"""
            <div style="background:#1a1a2e;border-radius:10px;padding:12px 16px;margin:10px 0;border-left:4px solid #f59e0b;">
              <span style="color:#fde68a;font-size:13px;">{result.overall_advice}</span>
            </div>""", unsafe_allow_html=True)

            # ── Summary tweak ─────────────────────────────────────────────────
            st.markdown('<p class="section-title" style="margin-top:16px;">Summary — Before vs After</p>', unsafe_allow_html=True)
            s1, s2 = st.columns(2)
            with s1:
                st.markdown("**Original**")
                st.markdown(f'<div style="background:#1a1a2e;padding:12px;border-radius:8px;color:#9ca3af;font-size:13px;border-left:3px solid #4b5563;">{result.summary_tweak.original}</div>', unsafe_allow_html=True)
            with s2:
                st.markdown("**Tweaked**")
                st.markdown(f'<div style="background:#1a1a2e;padding:12px;border-radius:8px;color:#e2e8f0;font-size:13px;border-left:3px solid #7c3aed;">{result.summary_tweak.tweaked}</div>', unsafe_allow_html=True)
            st.caption(f"Why: {result.summary_tweak.reason}")

            # ── Bullet tweaks ─────────────────────────────────────────────────
            if result.bullet_tweaks:
                st.markdown('<p class="section-title" style="margin-top:16px;">Experience Bullets — Before vs After</p>', unsafe_allow_html=True)
                for bt in result.bullet_tweaks:
                    st.markdown(f"**{bt.section}**")
                    b1, b2 = st.columns(2)
                    with b1:
                        st.markdown(f'<div style="background:#1a1a2e;padding:10px;border-radius:8px;color:#9ca3af;font-size:12px;border-left:3px solid #4b5563;">{bt.original}</div>', unsafe_allow_html=True)
                    with b2:
                        st.markdown(f'<div style="background:#1a1a2e;padding:10px;border-radius:8px;color:#e2e8f0;font-size:12px;border-left:3px solid #22c55e;">{bt.tweaked}</div>', unsafe_allow_html=True)
                    st.caption(f"Why: {bt.reason}")
                    st.markdown("")

            # ── Keywords + Skills ─────────────────────────────────────────────
            k1, k2 = st.columns(2)
            with k1:
                if result.keywords_to_add:
                    st.markdown('<p class="section-title">Keywords to Add</p>', unsafe_allow_html=True)
                    for kw in result.keywords_to_add:
                        st.markdown(f"""
                        <div style="background:#1a1a2e;border-radius:8px;padding:8px 12px;margin-bottom:6px;">
                          <span style="color:#c4b5fd;font-weight:600;">{kw.keyword}</span>
                          <span style="color:#6b7280;font-size:11px;"> &rarr; {kw.where_to_add}</span><br>
                          <span style="color:#9ca3af;font-size:11px;">{kw.reason}</span>
                        </div>""", unsafe_allow_html=True)

            with k2:
                if result.skills_to_highlight:
                    st.markdown('<p class="section-title">Skills to Move to Top</p>', unsafe_allow_html=True)
                    st.markdown(tags_html(result.skills_to_highlight, "tag-green"), unsafe_allow_html=True)

                if result.do_not_change:
                    st.markdown('<p class="section-title" style="margin-top:12px;">Already Well Aligned</p>', unsafe_allow_html=True)
                    st.markdown(tags_html(result.do_not_change, "tag-blue"), unsafe_allow_html=True)
