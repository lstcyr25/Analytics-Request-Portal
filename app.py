import base64
from pathlib import Path
from datetime import datetime

import streamlit as st

from services.auth_service import sign_in, get_current_profile, sign_out
from services.request_service import submit_request, get_my_requests
from services.lookup_service import (
    get_request_types,
    get_priorities,
    get_statuses,
)
from services.messaging_service import get_request_messages, send_message
from services.analyst_service import (
    update_request_status,
    add_internal_note,
    request_deadline_extension,
    escalate_request,
    get_analyst_performance,
)
from services.analytics_service import (
    get_analyst_workload,
    get_turnaround_by_type,
    get_overdue_requests,
    get_request_volume_by_department_and_type,
    get_analyst_performance_snapshots,
    get_completion_performance,
    generate_analyst_performance_snapshots,
)
from services.manager_service import (
    get_all_requests,
    get_analysts,
    assign_request,
    get_user_management_data,
    change_user_role,
)
from services.deliverable_service import (
    upload_request_deliverable,
    get_request_deliverables,
    download_request_deliverable,
    confirm_request_completion,
    request_changes,
)
from services.notification_service import (
    create_in_app_notification,
    get_user_notifications,
    mark_notification_read,
    mark_all_notifications_read,
)
from zoneinfo import ZoneInfo

# =========================================================
# PAGE CONFIGURATION
# =========================================================

st.set_page_config(
    page_title="Analytics Request Portal",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)


# =========================================================
# CONSTANTS AND IMAGE PATHS
# =========================================================

PORTAL_NAME = "Analytics Request Portal"

PROJECT_DIRECTORY = Path(__file__).resolve().parent

LANDING_BANNER_PATH = PROJECT_DIRECTORY / "landing_page_banner.jpg"
LOGIN_BANNER_PATH = PROJECT_DIRECTORY / "login_page_banner.jpg"


def load_image_as_base64(image_path):
    """Load a local image and return a Base64 data URI."""
    if not image_path.is_file():
        return None

    encoded_image = base64.b64encode(
        image_path.read_bytes()
    ).decode("utf-8")

    return f"data:image/jpeg;base64,{encoded_image}"


ROLE_TITLES = {
    "business_user": "Business User",
    "analyst": "Analytics Analyst",
    "analytics_manager": "Analytics Manager",
}

ROLE_NAVIGATION = {
    "business_user": [
        ("Dashboard", "dashboard"),
        ("Submit Request", "submit_request"),
        ("My Requests", "my_requests"),
        ("Messages", "messages"),
    ],
    "analyst": [
        ("Dashboard", "dashboard"),
        ("Assigned Requests", "assigned_requests"),
        ("Deadlines", "deadlines"),
        ("Messages", "messages"),
        ("Performance", "performance"),
    ],
    "analytics_manager": [
        ("Dashboard", "dashboard"),
        ("Assigned Requests", "assigned_requests"),
        ("All Requests", "all_requests"),
        ("Assignments", "assignments"),
        ("Team Workload", "team_workload"),
        ("Overdue Requests", "overdue_requests"),
        ("Analytics", "analytics"),
        ("User Management", "user_management"),
    ],
}


# =========================================================
# SESSION STATE
# =========================================================

if "page" not in st.session_state:
    st.session_state["page"] = "home"

if "dashboard_section" not in st.session_state:
    st.session_state["dashboard_section"] = "dashboard"

if "authenticated_profile" not in st.session_state:
    st.session_state["authenticated_profile"] = None


# =========================================================
# GLOBAL STYLING
# =========================================================

st.markdown(
    """
    <style>

    /* General application */

    .stApp {
        background: #ffffff;
        color: #171717;
    }

    .block-container {
        max-width: 1450px;
        padding-top: 1rem;
        padding-bottom: 2rem;
    }

    header[data-testid="stHeader"],
    [data-testid="stToolbar"],
    #MainMenu,
    footer {
        display: none !important;
    }

    h1, h2, h3, h4 {
        color: #171717 !important;
    }

    .stMarkdown,
    .stMarkdown p,
    .stMarkdown li {
        color: #252525;
    }


    /* Buttons */

    div.stButton > button,
    div.stFormSubmitButton > button {
        background-color: #168342;
        color: #ffffff !important;
        border: 1px solid #168342;
        border-radius: 6px;
        font-weight: 650;
        min-height: 42px;
    }

    div.stButton > button:hover,
    div.stFormSubmitButton > button:hover {
        background-color: #106b35;
        border-color: #106b35;
        color: #ffffff !important;
    }


    /* Navigation */

    .st-key-nav_home button,
    .st-key-nav_dashboard button,
    .st-key-nav_submit_request button,
    .st-key-nav_my_requests button,
    .st-key-nav_messages button,
    .st-key-nav_assigned_requests button,
    .st-key-nav_deadlines button,
    .st-key-nav_performance button,
    .st-key-nav_all_requests button,
    .st-key-nav_assignments button,
    .st-key-nav_team_workload button,
    .st-key-nav_overdue_requests button,
    .st-key-nav_analytics button {
        background: #ffffff;
        color: #171717 !important;
        border: 1px solid transparent;
    }

    .st-key-nav_home button:hover,
    .st-key-nav_dashboard button:hover,
    .st-key-nav_submit_request button:hover,
    .st-key-nav_my_requests button:hover,
    .st-key-nav_messages button:hover,
    .st-key-nav_assigned_requests button:hover,
    .st-key-nav_deadlines button:hover,
    .st-key-nav_performance button:hover,
    .st-key-nav_all_requests button:hover,
    .st-key-nav_assignments button:hover,
    .st-key-nav_team_workload button:hover,
    .st-key-nav_overdue_requests button:hover,
    .st-key-nav_analytics button:hover {
        color: #168342 !important;
        border-color: #168342;
    }


    /* Branding */

    .brand {
        display: flex;
        align-items: center;
        gap: 10px;
        color: #171717;
        font-size: 21px;
        font-weight: 800;
        padding-top: 7px;
    }

    .brand-mark {
        display: inline-block;
        width: 27px;
        height: 27px;
        background: #168342;
        border-radius: 7px;
        flex-shrink: 0;
    }

    .navbar-divider {
        border-bottom: 1px solid #eeeeee;
        margin: 8px 0 22px 0;
    }


    /* Landing page hero */

    .hero {
        display: grid;
        grid-template-columns: 1fr 1fr;
        width: 100%;
        min-height: 390px;
        background: #111111;
        overflow: hidden;
        border-radius: 0;
        align-items: stretch;
    }

    .hero-copy {
        background: #111111;
        color: #ffffff;
        padding: 40px 35px;
        display: flex;
        flex-direction: column;
        justify-content: center;
        box-sizing: border-box;
    }

    .hero-copy .eyebrow {
        color: #35d27c !important;
        font-weight: 800;
        letter-spacing: 1px;
        font-size: 14px;
        text-transform: uppercase;
        margin-bottom: 12px;
    }

    .hero-copy h1 {
        color: #ffffff !important;
        font-size: clamp(34px, 3.5vw, 48px);
        line-height: 1.08;
        font-weight: 850;
        margin: 0 0 18px 0;
    }

    .hero-copy p {
        color: #d0d0d0 !important;
        font-size: 17px;
        line-height: 1.6;
        margin: 0 0 12px 0;
    }

    .hero-image {
        width: 100%;
        height: 390px;
        min-width: 0;
        display: flex;
        align-items: center;
        justify-content: center;
        overflow: hidden;
        background: #ffffff;
    }

    .hero-image img {
        display: block;
        width: 100%;
        height: 100%;
        object-fit: contain;
        object-position: center;
    }


    /* Landing page sections */

    .section {
        padding: 42px 0 22px 0;
    }

    .section h2 {
        font-size: 29px;
        font-weight: 800;
        margin-bottom: 22px;
    }

    .step-card {
        border: 2px solid #202020;
        border-radius: 12px;
        padding: 25px;
        min-height: 175px;
        background: #ffffff;
    }

    .step-number {
        color: #168342;
        font-size: 39px;
        font-weight: 850;
    }

    .step-card h3 {
        font-size: 19px;
        margin: 5px 0;
    }

    .step-card p {
        color: #505866 !important;
        line-height: 1.5;
    }

    .role-card {
        border: 1px solid #dddddd;
        border-radius: 10px;
        padding: 22px;
        min-height: 150px;
        background: #ffffff;
    }

    .site-footer {
        background: #111111;
        color: #ffffff;
        padding: 22px 5%;
        margin-top: 35px;
        font-size: 14px;
    }


    /* Login page */

    .login-heading {
        font-size: 36px;
        font-weight: 850;
        color: #171717;
        margin-bottom: 8px;
    }

    .login-subtitle {
        color: #606060 !important;
        margin-bottom: 25px;
    }

    .login-visual {
        background: transparent;
        border-radius: 12px;
        min-height: 440px;
        padding: 0;
        display: flex;
        align-items: center;
        justify-content: center;
        border: 1px solid #245b3b;
        overflow: hidden;
    }

    .login-visual img {
        display: block;
        width: 100%;
        height: 100%;
        min-height: 440px;
        max-height: 560px;
        object-fit: contain;
        object-position: center;
    }

    .login-footer {
        text-align: center;
        color: #777777;
        font-size: 13px;
        padding: 25px 0;
    }


    /* Dashboard */

    .account-label {
        text-align: right;
        color: #606060;
        font-size: 12px;
        padding-top: 4px;
    }

    .dashboard-intro {
        background: #f7f7f7;
        border-left: 4px solid #168342;
        padding: 18px 22px;
        border-radius: 5px;
        margin: 15px 0 25px 0;
    }

    .dashboard-card {
        border: 1px solid #dedede;
        border-radius: 10px;
        padding: 22px;
        min-height: 145px;
        background: #ffffff;
    }

    .dashboard-card h3 {
        margin-top: 0;
    }


    /* Responsive layout */

    @media (max-width: 800px) {

        .hero {
            grid-template-columns: 1fr;
        }

        .hero-copy {
            min-height: 300px;
            padding: 35px 25px;
        }

        .hero-image {
            height: auto;
            min-height: 220px;
        }

        .hero-image img {
            height: auto;
            max-height: 320px;
        }

        .login-visual {
            min-height: 300px;
        }
    }

    </style>
    """,
    unsafe_allow_html=True,
)


# =========================================================
# NAVIGATION HELPERS
# =========================================================

def navigate_to(page):
    st.session_state["page"] = page


def navigate_to_section(section):
    st.session_state["dashboard_section"] = section


def clear_local_authentication():
    st.session_state["authenticated_profile"] = None
    st.session_state.pop("_supabase_client", None)
    st.session_state["page"] = "home"
    st.session_state["dashboard_section"] = "dashboard"


def handle_logout():
    result = sign_out()
    clear_local_authentication()

    if not result.get("success", False):
        st.session_state["logout_message"] = (
            "Your local session was cleared. "
            "The server reported an issue while signing out."
        )

    st.rerun()


# =========================================================
# PUBLIC NAVIGATION
# =========================================================

def render_public_navbar():
    brand, home, how, roles, contact, login = st.columns(
        [4.0, 0.8, 1.3, 0.7, 0.9, 1.0],
        vertical_alignment="center",
    )

    with brand:
        st.markdown(
            """
            <div class="brand">
                <span class="brand-mark"></span>
                Analytics Request Portal
            </div>
            """,
            unsafe_allow_html=True,
        )

    with home:
        st.button(
            "Home",
            key="nav_home",
            use_container_width=True,
            on_click=navigate_to,
            args=("home",),
        )

    with how:
        st.markdown(
            '<a href="#how-it-works" style="color:#171717;'
            'text-decoration:none;font-weight:600;">How it works</a>',
            unsafe_allow_html=True,
        )

    with roles:
        st.markdown(
            '<a href="#roles" style="color:#171717;'
            'text-decoration:none;font-weight:600;">Roles</a>',
            unsafe_allow_html=True,
        )

    with contact:
        st.markdown(
            '<a href="#contact" style="color:#171717;'
            'text-decoration:none;font-weight:600;">Contact</a>',
            unsafe_allow_html=True,
        )

    with login:
        st.button(
            "Log in",
            key="nav_login",
            use_container_width=True,
            type="primary",
            on_click=navigate_to,
            args=("login",),
        )

    st.markdown(
        '<div class="navbar-divider"></div>',
        unsafe_allow_html=True,
    )


# =========================================================
# LANDING PAGE
# =========================================================


def render_landing_page():
    render_public_navbar()

    landing_image = load_image_as_base64(LANDING_BANNER_PATH)

    if not landing_image:
        st.error("Could not load landing_page_banner.jpg.")
        return

    hero_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">

        <style>
            * {{
                box-sizing: border-box;
            }}

            html, body {{
                margin: 0;
                padding: 0;
                width: 100%;
                font-family: Arial, Helvetica, sans-serif;
                background: white;
            }}

            .hero {{
                width: 100%;
                min-height: 390px;
                display: grid;
                grid-template-columns: 1fr 1fr;
                background: #111111;
                overflow: hidden;
            }}

            .hero-copy {{
                padding: 40px 35px;
                display: flex;
                flex-direction: column;
                justify-content: center;
                background: #111111;
            }}

            .eyebrow {{
                color: #35d27c;
                font-size: 14px;
                font-weight: 800;
                letter-spacing: 1px;
                margin-bottom: 14px;
            }}

            h1 {{
                color: #ffffff;
                font-size: clamp(34px, 3.5vw, 48px);
                line-height: 1.08;
                font-weight: 850;
                margin: 0 0 18px 0;
            }}

            .hero-copy p {{
                color: #d0d0d0;
                font-size: 17px;
                line-height: 1.6;
                margin: 0 0 12px 0;
            }}

            .hero-image {{
                width: 100%;
                height: 390px;
                display: flex;
                justify-content: center;
                align-items: center;
                overflow: hidden;
                background: #111111;
            }}

            .hero-image img {{
                display: block;
                width: 100%;
                height: 100%;
                object-fit: contain;
                object-position: center;
            }}

            @media (max-width: 700px) {{
                .hero {{
                    grid-template-columns: 1fr;
                }}

                .hero-copy {{
                    min-height: 300px;
                    padding: 35px 25px;
                }}

                .hero-image {{
                    height: auto;
                    min-height: 220px;
                }}

                .hero-image img {{
                    height: auto;
                    max-height: 320px;
                }}
            }}
        </style>
    </head>

    <body>
        <div class="hero">

            <div class="hero-copy">
                <div class="eyebrow">
                    ONE PLACE FOR EVERY REQUEST
                </div>

                <h1>
                    From question to<br>insight, tracked.
                </h1>

                <p>
                    Business users ask. Analysts deliver.
                    Managers see the full picture.
                </p>

                <p>
                    A centralized workspace for submitting,
                    assigning, tracking, and delivering analytics work.
                </p>
            </div>

            <div class="hero-image">
                <img
                    src="{landing_image}"
                    alt="Analytics Request Portal landing page"
                >
            </div>

        </div>
    </body>
    </html>
    """

    st.components.v1.html(
        hero_html,
        height=410,
        scrolling=False,
    )

    # Get started button.
    button_columns = st.columns([1, 1])

    with button_columns[0]:
        if st.button(
            "Get started",
            key="get_started",
            type="primary",
        ):
            navigate_to("login")
            st.rerun()

    # How it works.
    st.markdown(
        """
        <div class="section" id="how-it-works">
            <h2>How it works</h2>
        </div>
        """,
        unsafe_allow_html=True,
    )

    step_columns = st.columns(3)

    steps = [
        ("1", "Submit", "Describe what you need and set a priority."),
        (
            "2",
            "Get assigned",
            "The request goes to an analyst based on workload and skills.",
        ),
        (
            "3",
            "Receive results",
            "Review the final product and confirm it.",
        ),
    ]

    for column, step in zip(step_columns, steps):
        with column:
            st.markdown(
                f"""
                <div class="step-card">
                    <div class="step-number">{step[0]}</div>
                    <h3>{step[1]}</h3>
                    <p>{step[2]}</p>
                </div>
                """,
                unsafe_allow_html=True,
            )

    # Roles.
    st.markdown(
        """
        <div class="section" id="roles">
            <h2>Designed for every role</h2>
        </div>
        """,
        unsafe_allow_html=True,
    )

    role_columns = st.columns(3)

    role_cards = [
        (
            "Business Users",
            "Submit requests, communicate with analysts, and track delivery.",
        ),
        (
            "Analysts",
            "Manage assignments, update progress, and deliver analytics.",
        ),
        (
            "Analytics Managers",
            "Oversee workloads, assignments, deadlines, and performance.",
        ),
    ]

    for column, (title, description) in zip(role_columns, role_cards):
        with column:
            st.markdown(
                f"""
                <div class="role-card">
                    <h3>{title}</h3>
                    <p>{description}</p>
                </div>
                """,
                unsafe_allow_html=True,
            )

    # Footer.
    st.markdown(
        """
        <div class="section" id="contact">
            <h2>Ready to get started?</h2>
            <p>
                Bring your analytics requests into one organized workspace.
            </p>
        </div>

        <div class="site-footer">
            Analytics Request Portal · CIS 4910 Capstone
        </div>
        """,
        unsafe_allow_html=True,
    )


# =========================================================
# LOGIN PAGE
# =========================================================

def render_login_page():
    render_public_navbar()

    st.markdown("<br>", unsafe_allow_html=True)

    login_column, visual_column = st.columns(
        [1.05, 0.95],
        gap="large",
    )

    with login_column:
        st.markdown(
            """
            <div class="login-heading">Welcome back.</div>
            <p class="login-subtitle">
                Sign in to access your analytics workspace.
            </p>
            """,
            unsafe_allow_html=True,
        )

        with st.form("login_form"):
            st.subheader("Log in")

            email = st.text_input(
                "Username / Email",
                placeholder="Enter your email address",
            )

            password = st.text_input(
                "Password",
                type="password",
                placeholder="Enter your password",
            )

            submitted = st.form_submit_button(
                "Log in",
                use_container_width=True,
                type="primary",
            )

        if submitted:
            if not email.strip() or not password:
                st.error("Enter both your email address and password.")

            else:
                with st.spinner("Signing in..."):
                    result = sign_in(email.strip(), password)

                if not result.get("success", False):
                    st.error(result.get("error", "Sign-in failed."))

                else:
                    profile_result = get_current_profile()

                    if not profile_result.get("success", False):
                        sign_out()
                        st.session_state.pop("_supabase_client", None)

                        st.error(
                            profile_result.get(
                                "error",
                                "Your user profile could not be loaded.",
                            )
                        )

                    else:
                        profile = profile_result["profile"]
                        role = profile.get("role")

                        if role not in ROLE_TITLES:
                            sign_out()
                            st.session_state.pop("_supabase_client", None)
                            st.error("Your account has an invalid role.")

                        else:
                            st.session_state["authenticated_profile"] = profile
                            st.session_state["page"] = "dashboard"
                            st.session_state["dashboard_section"] = "dashboard"
                            st.rerun()

        st.markdown(
            """
            <p style="color:#777777;font-size:13px;margin-top:15px;">
                Need access? Contact your Analytics Portal administrator.
            </p>
            """,
            unsafe_allow_html=True,
        )

    with visual_column:
        login_image = load_image_as_base64(LOGIN_BANNER_PATH)

        if login_image:
            st.markdown(
                f"""
                <div class="login-visual">
                    <img
                        src="{login_image}"
                        alt="Analytics Request Portal login image"
                    >
                </div>
                """,
                unsafe_allow_html=True,
            )
        else:
            st.error(
                "Login image not found. Make sure "
                "login_page_banner.jpg is in the same folder as app.py."
            )

    st.markdown(
        """
        <div class="login-footer">
            Analytics Request Portal · CIS 4910 Capstone
        </div>
        """,
        unsafe_allow_html=True,
    )


# =========================================================
# AUTHENTICATED NAVIGATION
# =========================================================

def render_authenticated_navbar(profile):
    role = profile["role"]
    navigation = ROLE_NAVIGATION[role]

    brand, account, notifications, logout = st.columns(
        [3.0, 2.0, 1.2, 1.0],
        vertical_alignment="center",
    )

    with brand:
        st.markdown(
            """
            <div class="brand">
                <span class="brand-mark"></span>
                Analytics Request Portal
            </div>
            """,
            unsafe_allow_html=True,
        )

    with account:
        st.markdown(
            f"""
            <div class="account-label">
                Signed in as <strong>{profile['full_name']}</strong><br>
                {ROLE_TITLES[role]}
            </div>
            """,
            unsafe_allow_html=True,
        )

    with notifications:
        notification_result = get_user_notifications()

        if notification_result["success"]:
            unread_count = notification_result["unread_count"]
            notification_items = notification_result["notifications"]

            bell_label = (
                f"🔔 {unread_count}"
                if unread_count > 0
                else "🔔"
            )

            with st.popover(bell_label, use_container_width=True):
                st.markdown("### Notifications")

                if unread_count > 0:
                    if st.button(
                        "Mark all as read",
                        key="mark_all_notifications_read",
                        use_container_width=True,
                    ):
                        result = mark_all_notifications_read()

                        if result["success"]:
                            st.rerun()
                        else:
                            st.error(result["error"])

                if not notification_items:
                    st.info("You're all caught up.")

                for item in notification_items:
                    with st.container(border=True):
                        if not item["is_read"]:
                            st.markdown(
                                f"**● {item['title']}**"
                            )
                        else:
                            st.markdown(item["title"])

                        st.caption(item["message"])

                        if item.get("request_id"):
                            st.caption(
                                f"Request #{item['request_id']}"
                            )

                        if not item["is_read"]:
                            if st.button(
                                "Mark as read",
                                key=f"read_notification_{item['notification_id']}",
                            ):
                                result = mark_notification_read(
                                    item["notification_id"]
                                )

                                if result["success"]:
                                    st.rerun()
                                else:
                                    st.error(result["error"])
        else:
            st.button("🔔", disabled=True)

    with logout:
        st.button(
            "Sign Out",
            key="authenticated_sign_out",
            type="primary",
            use_container_width=True,
            on_click=handle_logout,
        )

    st.markdown(
        '<div class="navbar-divider"></div>',
        unsafe_allow_html=True,
    )

    nav_columns = st.columns(len(navigation))

    for column, (label, section) in zip(nav_columns, navigation):
        with column:
            st.button(
                label,
                key=f"nav_{section}",
                use_container_width=True,
                type=(
                    "primary"
                    if st.session_state["dashboard_section"] == section
                    else "secondary"
                ),
                on_click=navigate_to_section,
                args=(section,),
            )


# =========================================================
# DASHBOARD HOME PAGES
# =========================================================


def render_dashboard_cards(cards):
    columns = st.columns(len(cards))

    for column, (icon, title, description, section) in zip(columns, cards):
        with column:
            with st.container(border=True):
                st.markdown(f"### {icon} {title}")
                st.write(description)

                st.button(
                    f"Open {title}",
                    key=f"dashboard_{section}",
                    use_container_width=True,
                    on_click=navigate_to_section,
                    args=(section,),
                )


def render_business_dashboard(profile):
    st.title("Business User Dashboard")
    st.write(f"Welcome, **{profile['full_name']}**.")

    st.markdown("### Your analytics workspace")

    render_dashboard_cards(
        [
            (
                "📝",
                "Submit Request",
                "Submit a new analytics request to the team.",
                "submit_request",
            ),
            (
                "📋",
                "My Requests",
                "Track the status and progress of your requests.",
                "my_requests",
            ),
            (
                "💬",
                "Messages",
                "Communicate with analysts about your requests.",
                "messages",
            ),
        ]
    )


def render_analyst_dashboard(profile):
    st.title("Analyst Dashboard")
    st.write(f"Welcome, **{profile['full_name']}**.")

    st.markdown("### Your analytics workspace")

    render_dashboard_cards(
        [
            (
                "📥",
                "Assigned Requests",
                "Review and manage assigned work.",
                "assigned_requests",
            ),
            (
                "⏰",
                "Deadlines",
                "Monitor delivery dates and overdue work.",
                "deadlines",
            ),
            (
                "📊",
                "Performance",
                "Review workload and completion performance.",
                "performance",
            ),
        ]
    )

def render_assigned_requests_page(profile):
    """Display requests assigned to the currently authenticated user."""

    st.title("Assigned Requests")
    st.write("Review the analytics requests assigned to you.")

    analyst_id = profile.get("user_id")

    if not analyst_id:
        st.error("Your analyst profile could not be identified.")
        return

    # Retrieve requests visible to the authenticated user.
    requests_result = get_my_requests()

    if not requests_result.get("success"):
        st.error(
            "Could not retrieve assigned requests: "
            + requests_result.get("error", "Unknown error")
        )
        return

    # RLS restricts access; this filter selects the analyst's assignments.
    assigned_requests = [
        request
        for request in requests_result.get("data", [])
        if request.get("assigned_to") == analyst_id
    ]

    # Retrieve lookup information.
    types_result = get_request_types()
    priorities_result = get_priorities()
    statuses_result = get_statuses()

    for result, label in [
        (types_result, "request types"),
        (priorities_result, "priorities"),
        (statuses_result, "statuses"),
    ]:
        if not result.get("success"):
            st.error(
                f"Could not retrieve {label}: "
                + result.get("error", "Unknown error")
            )
            return

    type_map = {
        item["type_id"]: item["type_name"]
        for item in types_result.get("data", [])
    }

    priority_map = {
        item["priority_id"]: item["priority_name"]
        for item in priorities_result.get("data", [])
    }

    status_map = {
        item["status_id"]: item["status_name"]
        for item in statuses_result.get("data", [])
    }

    if not assigned_requests:
        st.info("You currently have no assigned requests.")
        return

    # Sort newest requests first.
    assigned_requests.sort(
        key=lambda item: item.get("created_at") or "",
        reverse=True,
    )

    # Summary metrics.
    total_requests = len(assigned_requests)

    overdue_requests = sum(
        1 for item in assigned_requests
        if item.get("is_overdue")
    )

    in_progress_requests = sum(
        1 for item in assigned_requests
        if status_map.get(item.get("status_id")) == "In Progress"
    )

    col1, col2, col3 = st.columns(3)

    col1.metric("Assigned Requests", total_requests)
    col2.metric("In Progress", in_progress_requests)
    col3.metric("Overdue", overdue_requests)

    st.divider()

    # Prepare the request overview.
    display_rows = []

    for request in assigned_requests:
        display_rows.append({
            "Request ID": request["request_id"],
            "Title": request.get("title", ""),
            "Request Type": type_map.get(
                request.get("type_id"), "Unknown"
            ),
            "Priority": priority_map.get(
                request.get("priority_id"), "Unknown"
            ),
            "Status": status_map.get(
                request.get("status_id"), "Unknown"
            ),
            "Expected Date": request.get("expected_date") or "Not set",
            "Overdue": "Yes" if request.get("is_overdue") else "No",
        })

    st.subheader("Your Request Queue")

    st.dataframe(
        display_rows,
        use_container_width=True,
        hide_index=True,
    )

    st.divider()
    st.subheader("Request Details")

    request_options = {
        request["request_id"]: request
        for request in assigned_requests
    }

    selected_request_id = st.selectbox(
        "Select a request to view its details",
        options=list(request_options.keys()),
        format_func=lambda request_id: (
            f"#{request_id} - "
            f"{request_options[request_id].get('title', 'Untitled')}"
        ),
        key="analyst_selected_request",
    )

    selected_request = request_options[selected_request_id]

    st.markdown(f"### {selected_request.get('title', 'Untitled')}")

    detail_col1, detail_col2 = st.columns(2)

    with detail_col1:
        st.write(
            "**Request ID:**",
            selected_request.get("request_id"),
        )
        st.write(
            "**Request Type:**",
            type_map.get(selected_request.get("type_id"), "Unknown"),
        )
        st.write(
            "**Priority:**",
            priority_map.get(
                selected_request.get("priority_id"), "Unknown"
            ),
        )
        st.write(
            "**Status:**",
            status_map.get(selected_request.get("status_id"), "Unknown"),
        )

    with detail_col2:
        st.write(
            "**Needed By:**",
            selected_request.get("needed_date") or "Not specified",
        )
        st.write(
            "**Expected Date:**",
            selected_request.get("expected_date") or "Not set",
        )
        st.write(
            "**Overdue:**",
            "Yes" if selected_request.get("is_overdue") else "No",
        )

    st.markdown("**Description**")
    st.write(
        selected_request.get("description") or "No description provided."
    )

    created_at = selected_request.get("created_at")

    if created_at:
        st.caption(f"Submitted: {created_at}")


    st.divider()
    st.subheader("Request Workflow")

    current_status = status_map.get(
        selected_request.get("status_id"),
        "Unknown",
    )

    status_id_map = {
        item["status_name"]: item["status_id"]
        for item in statuses_result.get("data", [])
    }

    def apply_status_change(new_status_name, reason):
        result = update_request_status(
            request_id=selected_request_id,
            new_status_id=status_id_map[new_status_name],
            reason=reason,
        )

        if result.get("success"):
            notification = result.get("notification", {})

            if notification.get("success"):
                st.success(
                    f"Request moved to {new_status_name}. "
                    "Requester notification was accepted."
                )
            else:
                st.warning(
                    f"Request moved to {new_status_name}, but the "
                    "requester notification could not be completed."
                )

            st.rerun()

        else:
            st.error(
                "Status update failed: "
                + result.get("error", "Unknown error")
            )

    if current_status == "Assigned":
        st.caption(
            "This request is assigned to you. Start working when ready."
        )

        if st.button(
            "Start Working",
            key=f"start_working_{selected_request_id}",
            use_container_width=True,
        ):
            apply_status_change(
                "In Progress",
                "Analyst started working on the request.",
            )

    elif current_status == "In Progress":
        st.caption(
            "When your work is finished, choose how you want to "
            "complete this request."
        )

        # Direct completion for work that does not require a file.
        st.markdown("**Complete without a deliverable**")

        completion_note = st.text_area(
            "Completion note",
            placeholder=(
                "Explain what you fixed, changed, or completed..."
            ),
            key=f"completion_note_{selected_request_id}",
        )

        if st.button(
            "Complete Request",
            key=f"complete_request_{selected_request_id}",
            use_container_width=True,
            disabled=len(completion_note.strip()) < 5,
        ):
            apply_status_change(
                "Closed",
                completion_note.strip(),
            )

        st.divider()

        # Optional file-based requester review.
        st.markdown("**Submit work with a deliverable**")

        deliverables_result = get_request_deliverables(
            selected_request_id
        )

        has_deliverables = (
            deliverables_result.get("success")
            and bool(deliverables_result.get("deliverables"))
        )

        if has_deliverables:
            if st.button(
                "Submit for Requester Review",
                key=f"submit_review_{selected_request_id}",
                use_container_width=True,
            ):
                apply_status_change(
                    "Awaiting Confirmation",
                    "Analyst submitted completed work for requester review.",
                )
        else:
            st.info(
                "Upload at least one deliverable below to enable "
                "requester review. This is optional if the work "
                "does not require a file."
            )

    elif current_status == "Escalated":
        st.info("This request has been escalated.")

        if st.button(
            "Resume Work",
            key=f"resume_work_{selected_request_id}",
            use_container_width=True,
        ):
            apply_status_change(
                "In Progress",
                "Analyst resumed work on the escalated request.",
            )

    elif current_status == "Awaiting Confirmation":
        st.info(
            "Your work has been submitted and is waiting for the "
            "requester's review."
        )

    else:
        st.info(
            "No status updates are currently available for this request."
        )

    if current_status != "In Progress":
        st.info(
            "Move this request to In Progress before uploading deliverables."
        )

    else:

                    st.caption(
                        "Upload completed reports, spreadsheets, dashboards, "
                        "or other files for the requester."
                    )

                    with st.form(
                        key=f"deliverable_upload_form_{selected_request_id}"
                    ):
                        uploaded_files = st.file_uploader(
                            "Select deliverable files",
                            accept_multiple_files=True,
                            key=f"deliverable_files_{selected_request_id}",
                        )

                        delivery_description = st.text_area(
                            "Delivery message (optional)",
                            placeholder="Explain what you completed or what the files contain...",
                        )

                        upload_submitted = st.form_submit_button(
                            "Upload Deliverables",
                            use_container_width=True,
                        )

                    if upload_submitted:
                        if not uploaded_files:
                            st.warning("Please select at least one file.")

                        else:
                            successful_uploads = 0

                            for uploaded_file in uploaded_files:
                                upload_result = upload_request_deliverable(
                                    request_id=selected_request_id,
                                    file=uploaded_file,
                                    description=delivery_description,
                                )

                                if upload_result.get("success"):
                                    successful_uploads += 1
                                    st.success(upload_result["message"])
                                else:
                                    st.error(
                                        f"{uploaded_file.name}: "
                                        f"{upload_result.get('error', 'Upload failed.')}"
                                    )

                            if successful_uploads:
                                st.info(
                                    f"{successful_uploads} deliverable(s) uploaded. "
                                    "You can now move the request to Awaiting Confirmation."
                                )

    st.divider()
    st.subheader("Private Internal Notes")

    with st.form(
        key=f"analyst_internal_note_form_{selected_request_id}"
    ):
        internal_note = st.text_area(
            "Add an internal note",
            placeholder=(
                "Record analysis findings, technical details, "
                "or internal updates..."
            ),
            height=120,
        )

        note_submitted = st.form_submit_button(
            "Save Internal Note",
            use_container_width=True,
        )

    if note_submitted:
        if not internal_note.strip():
            st.warning("Please enter a note before submitting.")

        else:
            note_result = add_internal_note(
                request_id=selected_request_id,
                note=internal_note,
            )

            if note_result.get("success"):
                st.success("Private internal note saved successfully.")

            else:
                st.error(
                    "Could not save internal note: "
                    + note_result.get("error", "Unknown error")
                )

    st.markdown("### Saved Internal Notes")

    notes_result = get_request_messages(selected_request_id)

    if not notes_result.get("success"):
        st.error(
            "Could not retrieve internal notes: "
            + notes_result.get("error", "Unknown error")
        )

    else:
        internal_notes = [
            message
            for message in notes_result.get("messages", [])
            if message.get("is_internal")
        ]

        internal_notes.sort(
            key=lambda note: note.get("created_at", ""),
            reverse=True,
        )

        with st.expander(
            f"Private Internal Notes ({len(internal_notes)})",
            expanded=False,
        ):
            if not internal_notes:
                st.info("No internal notes have been added to this request.")

            else:
                for note in internal_notes:
                    st.caption(
                        f"Added: {note.get('created_at', 'Unknown date')}"
                    )
                    st.write(note.get("message_body", ""))
                    st.divider()

    # =====================================================
    # DEADLINE EXTENSION REQUEST
    # =====================================================

    st.divider()
    st.subheader("Request Deadline Extension")

    st.write(
        "If additional time is needed, submit a proposed "
        "delivery date and explain the reason."
    )

    with st.form(
        key=f"analyst_deadline_extension_form_{selected_request_id}"
    ):
        new_expected_date = st.date_input(
            "Proposed New Expected Date",
            min_value=datetime.now().date(),
            format="MM/DD/YYYY",
        )

        extension_reason = st.text_area(
            "Reason for Extension",
            placeholder=(
                "Explain why additional time is needed..."
            ),
            height=120,
        )

        extension_submitted = st.form_submit_button(
            "Submit Deadline Extension",
            use_container_width=True,
        )

    if extension_submitted:
        if not extension_reason.strip():
            st.warning("Please provide a reason for the extension.")

        else:
            extension_result = request_deadline_extension(
                request_id=selected_request_id,
                new_expected_date=new_expected_date.isoformat(),
                reason=extension_reason,
            )

            if extension_result.get("success"):
                st.success(
                    "Deadline extension request submitted successfully."
                )

                notification = extension_result.get("notification", {})

                if notification.get("success"):
                    st.caption(
                        "Requester notification was accepted."
                    )
                else:
                    st.warning(
                        "The extension was recorded, but the requester "
                        "notification could not be completed."
                    )

            else:
                st.error(
                    "Deadline extension failed: "
                    + extension_result.get("error", "Unknown error")
                )


    # =====================================================
    # REQUEST ESCALATION
    # =====================================================

    st.divider()
    st.subheader("Escalate Request")

    st.write(
        "If this request requires management attention, "
        "provide a reason to escalate it."
    )

    st.info(
        "Submitting an escalation will notify all active "
        "analytics managers."
    )

    with st.form(
        key=f"analyst_escalation_form_{selected_request_id}"
    ):
        escalation_reason = st.text_area(
            "Reason for Escalation",
            placeholder=(
                "Explain why this request requires management attention..."
            ),
            height=120,
        )

        escalation_submitted = st.form_submit_button(
            "Escalate Request",
            use_container_width=True,
        )

    if escalation_submitted:
        if not escalation_reason.strip():
            st.warning("Please provide a reason for the escalation.")

        else:
            escalation_result = escalate_request(
                request_id=selected_request_id,
                reason=escalation_reason,
            )

            if escalation_result.get("success"):
                st.success(
                    "Request successfully escalated to management."
                )

                notification = escalation_result.get(
                    "notification", {}
                )

                if notification.get("success"):
                    st.caption(
                        "Manager notification was accepted."
                    )
                else:
                    st.warning(
                        "The request was escalated, but manager "
                        "notification could not be completed."
                    )

            else:
                st.error(
                    "Escalation failed: "
                    + escalation_result.get("error", "Unknown error")
                )



def render_manager_dashboard(profile):
    """Display the analytics manager's operational dashboard."""

    st.title("Analytics Manager Dashboard")
    st.write(f"Welcome, **{profile['full_name']}**.")

    st.caption("Overview of analytics operations and team performance.")

    # Retrieve manager-only analytics.
    with st.spinner("Loading manager dashboard..."):
        workload_result = get_analyst_workload()
        overdue_result = get_overdue_requests()
        completion_result = get_completion_performance()

    # Stop if any analytics query fails.
    errors = []

    for name, result in [
        ("Team workload", workload_result),
        ("Overdue requests", overdue_result),
        ("Completion performance", completion_result),
    ]:
        if not result.get("success"):
            errors.append(
                f"{name}: {result.get('error') or result.get('message', 'Unknown error')}"
            )

    if errors:
        st.error("Some dashboard information could not be loaded.")
        for error in errors:
            st.write(f"- {error}")
        return

    workload = workload_result.get("data", [])
    overdue_requests = overdue_result.get("data", [])
    completion = completion_result.get("data", {})

    # Calculate current team workload.
    total_open = sum(
        int(analyst.get("open_requests") or 0)
        for analyst in workload
    )

    analyst_count = len(workload)

    total_completed = completion.get("total_completed", 0)
    on_time_rate = completion.get("on_time_rate")

    # Main dashboard metrics.
    st.markdown("### Analytics Operations")

    col1, col2, col3, col4 = st.columns(4)

    col1.metric("Active Analysts", analyst_count)
    col2.metric("Open Requests", total_open)
    col3.metric("Overdue Requests", len(overdue_requests))

    col4.metric(
        "On-Time Completion",
        f"{on_time_rate:.1f}%" if on_time_rate is not None else "N/A",
    )

    st.divider()

    # Daily analyst performance snapshots.
    st.markdown("### Daily Performance Snapshots")

    st.write(
        "Generate or refresh today's performance snapshots "
        "for all active analysts."
    )

    if st.button(
        "Generate Daily Snapshots",
        key="generate_daily_snapshots",
        type="primary",
    ):
        with st.spinner("Generating daily performance snapshots..."):
            snapshot_result = generate_analyst_performance_snapshots()

        if snapshot_result.get("success"):
            st.success(snapshot_result.get("message"))

            st.write(
                f"Analyst snapshots generated: "
                f"{snapshot_result.get('snapshots_created', 0)}"
            )

        else:
            st.error(
                snapshot_result.get("message", "Unable to generate snapshots.")
            )

    st.divider()

    # Team workload.
    st.markdown("### Team Workload")

    if workload:
        workload_display = [
            {
                "Analyst": analyst.get("full_name", "Unknown"),
                "Open Requests": analyst.get("open_requests", 0),
                "Load Score": analyst.get("load_score", 0),
            }
            for analyst in workload
        ]

        st.dataframe(
            workload_display,
            use_container_width=True,
            hide_index=True,
        )

    else:
        st.info("No active analysts were found.")

    st.divider()

    # Completion performance.
    st.markdown("### Completion Performance")

    col1, col2, col3 = st.columns(3)

    col1.metric("Completed Requests", total_completed)
    col2.metric("Completed On Time", completion.get("on_time", 0))
    col3.metric("Completed Late", completion.get("overdue", 0))

    if on_time_rate is not None:
        st.progress(
            min(max(on_time_rate / 100, 0.0), 1.0)
        )
        st.caption(
            "Percentage of completed requests with an expected date "
            "that were resolved on or before their deadline."
        )
    else:
        st.info("On-time performance will appear after requests are completed with deadlines.")

    st.divider()

    # Overdue request monitoring.
    st.markdown("### Overdue Request Monitoring")

    if overdue_requests:
        st.warning(
            f"{len(overdue_requests)} request(s) currently require attention."
        )

        st.dataframe(
            overdue_requests,
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.success("There are currently no overdue requests.")

    st.caption(
        "Dashboard metrics are retrieved from the manager-authorized "
        "analytics services and Gold reporting views."
    )



def render_submit_request_page(profile):
    """Display and process the Business User request submission form."""

    if profile.get("role") != "business_user":
        st.error("You do not have permission to submit business requests.")
        return

    st.title("Submit an Analytics Request")

    st.write(
        "Tell our analytics team what you need. "
        "Your request will be assigned based on priority and analyst availability."
    )

    # Retrieve dropdown options from Supabase.
    request_types_result = get_request_types()
    priorities_result = get_priorities()

    if not request_types_result.get("success"):
        st.error(
            "Unable to load request types: "
            + request_types_result.get("error", "Unknown error")
        )
        return

    if not priorities_result.get("success"):
        st.error(
            "Unable to load priorities: "
            + priorities_result.get("error", "Unknown error")
        )
        return

    request_types = request_types_result.get("data", [])
    priorities = priorities_result.get("data", [])

    if not request_types:
        st.warning("No request types are currently available.")
        return

    if not priorities:
        st.warning("No priorities are currently available.")
        return

    st.markdown("### Request information")

    with st.form("business_request_form", clear_on_submit=True):

        request_title = st.text_input(
            "Request title",
            placeholder="Example: Monthly Sales Performance Dashboard",
            max_chars=150,
        )

        request_description = st.text_area(
            "Describe what you need",
            placeholder=(
                "Explain the business question, data needed, "
                "desired output, and any relevant details."
            ),
            height=180,
        )

        request_type = st.selectbox(
            "Request type",
            options=request_types,
            format_func=lambda item: item["type_name"],
        )

        priority = st.selectbox(
            "Priority",
            options=priorities,
            format_func=lambda item: item["priority_name"],
        )

        needed_date = st.date_input(
            "Needed by (optional)",
            value=None,
            format="MM/DD/YYYY",
        )

        submitted = st.form_submit_button(
            "Submit Request",
            type="primary",
            use_container_width=True,
        )

    if submitted:

        if not request_title.strip():
            st.error("Please enter a request title.")

        elif not request_description.strip():
            st.error("Please describe your request.")

        else:
            with st.spinner("Submitting your request..."):

                result = submit_request(
                    type_id=int(request_type["type_id"]),
                    priority_id=int(priority["priority_id"]),
                    title=request_title,
                    description=request_description,
                    needed_date=(
                        needed_date.isoformat()
                        if needed_date is not None
                        else None
                    ),
                )

            if result.get("success"):

                st.success(
                    f"Your request was submitted successfully! "
                    f"Request ID: #{result['request_id']}"
                )

                st.info(
                    "Your request has entered the assignment workflow. "
                    "You can track its progress under My Requests."
                )

                notifications = result.get("notifications", {})

                failed_notifications = [
                    notification
                    for notification in notifications.values()
                    if not notification.get("success", False)
                ]

                if failed_notifications:
                    st.warning(
                        "Your request was saved, but one or more email "
                        "notifications could not be delivered."
                    )

            else:
                st.error(
                    "Your request could not be submitted: "
                    + result.get("error", "An unexpected error occurred.")
                )


def render_my_requests_page(profile):
    """Display requests submitted by the authenticated business user."""

    if profile.get("role") != "business_user":
        st.error("You do not have permission to access this page.")
        return

    st.title("My Requests")
    st.write("View and track the progress of your analytics requests.")

    # Retrieve the user's requests.
    requests_result = get_my_requests()

    if not requests_result.get("success"):
        st.error(
            "Unable to retrieve your requests: "
            + requests_result.get("error", "Unknown error")
        )
        return

    requests = requests_result.get("data", [])

    if not requests:
        st.info(
            "You haven't submitted any requests yet. "
            "Select Submit Request to get started."
        )
        return

    # Retrieve readable lookup values.
    types_result = get_request_types()
    priorities_result = get_priorities()
    statuses_result = get_statuses()

    for result, label in [
        (types_result, "request types"),
        (priorities_result, "priorities"),
        (statuses_result, "statuses"),
    ]:
        if not result.get("success"):
            st.error(
                f"Unable to load {label}: "
                + result.get("error", "Unknown error")
            )
            return

    type_names = {
        item["type_id"]: item["type_name"]
        for item in types_result["data"]
    }

    priority_names = {
        item["priority_id"]: item["priority_name"]
        for item in priorities_result["data"]
    }

    status_names = {
        item["status_id"]: item["status_name"]
        for item in statuses_result["data"]
    }

    def display_date(value, include_time=False):
        if not value:
            return "Not specified"

        try:
            parsed = datetime.fromisoformat(
                str(value).replace("Z", "+00:00")
            )

            if include_time:
                return parsed.strftime("%m/%d/%Y %I:%M %p")

            return parsed.strftime("%m/%d/%Y")

        except (ValueError, TypeError):
            return str(value)

    pending_review_requests = [
        request for request in requests
        if request.get("status_id") == 5
    ]

    other_requests = [
        request for request in requests
        if request.get("status_id") != 5
    ]

    # Request overview.
    st.markdown("### Request overview")

    metric_col1, metric_col2 = st.columns(2)

    with metric_col1:
        st.metric("Total requests", len(requests))

    with metric_col2:
        st.metric("Awaiting your review", len(pending_review_requests))

    st.divider()

    # Display requests awaiting confirmation first.
    if pending_review_requests:
        st.markdown("### Needs Your Review")
        st.caption(
            "These requests have completed work waiting for your approval."
        )
    else:
        st.markdown("### All Submitted Requests")

    requests = pending_review_requests + other_requests
    other_section_shown = False

    for request in requests:
        if (
            request.get("status_id") != 5
            and not other_section_shown
        ):
            st.divider()
            st.markdown("### All Other Requests")
            other_section_shown = True

        request_id = request["request_id"]
        title = request.get("title") or "Untitled request"

        status = status_names.get(
            request.get("status_id"),
            "Unknown status",
        )

        priority = priority_names.get(
            request.get("priority_id"),
            "Unknown priority",
        )

        request_type = type_names.get(
            request.get("type_id"),
            "Unknown request type",
        )

        overdue = request.get("is_overdue", False)

        with st.expander(
            f"#{request_id} — {title}",
            expanded=False,
        ):

            if overdue:
                st.warning("This request is marked as overdue.")

            st.write(f"**Status:** {status}")
            st.write(f"**Priority:** {priority}")
            st.write(f"**Request type:** {request_type}")

            st.write(
                f"**Submitted:** "
                f"{display_date(request.get('created_at'), True)}"
            )

            st.write(
                f"**Needed by:** "
                f"{display_date(request.get('needed_date'))}"
            )

            st.write(
                f"**Expected delivery:** "
                f"{display_date(request.get('expected_date'))}"
            )

            st.write(
                f"**Description:** "
                f"{request.get('description') or 'No description provided.'}"
            )

            if request.get("resolved_at"):
                st.write(
                    f"**Resolved:** "
                    f"{display_date(request.get('resolved_at'), True)}"
                )

            st.divider()
            st.markdown("**Delivered Files**")

            deliverables_result = get_request_deliverables(
                request_id
            )

            if not deliverables_result.get("success"):
                st.error(
                    "Could not retrieve delivered files: "
                    + deliverables_result.get("error", "Unknown error")
                )

            else:
                deliverables = deliverables_result.get(
                    "deliverables", []
                )

                if not deliverables:
                    st.info(
                        "No deliverable files have been submitted yet."
                    )

                else:
                    for deliverable in deliverables:
                        st.write(
                            f"**{deliverable['file_name']}**"
                        )

                        if deliverable.get("description"):
                            st.caption(deliverable["description"])

                        st.caption(
                            f"Uploaded: {display_date(deliverable.get('uploaded_at'), True)}"
                        )

                        download_result = download_request_deliverable(
                            deliverable["storage_path"]
                        )

                        if download_result.get("success"):
                            st.download_button(
                                label=f"Download {deliverable['file_name']}",
                                data=download_result["file_bytes"],
                                file_name=deliverable["file_name"],
                                key=f"download_{deliverable['deliverable_id']}",
                                use_container_width=True,
                            )
                        else:
                            st.error(
                                "Download unavailable: "
                                + download_result.get("error", "Unknown error")
                            )


            if request.get("status_id") in (5, 6):
                st.divider()

                is_closed = request.get("status_id") == 6

                if is_closed:
                    st.markdown("**Reopen Completed Work**")
                    st.caption(
                        "If the completed work does not meet your "
                        "expectations, explain what needs to be revised."
                    )
                else:
                    st.markdown("**Review Completed Work**")
                    st.caption(
                        "Review and download the deliverables. "
                        "You can approve the work or request revisions."
                    )

                change_reason = st.text_area(
                    "Reason for requested changes",
                    key=f"change_reason_{request_id}",
                    placeholder=(
                        "Explain what needs to be corrected, "
                        "changed, or improved..."
                    ),
                    help="Please provide at least 5 characters.",
                )

                if not is_closed:
                    confirm_col, changes_col = st.columns(2)

                    with confirm_col:
                        if st.button(
                            "Confirm Completion",
                            key=f"confirm_completion_{request_id}",
                            type="primary",
                            use_container_width=True,
                        ):
                            confirmation_result = confirm_request_completion(
                                request_id
                            )

                            if confirmation_result.get("success"):
                                st.success(
                                    confirmation_result["message"]
                                )
                                st.rerun()
                            else:
                                st.error(
                                    confirmation_result.get(
                                        "error",
                                        "Could not confirm completion."
                                    )
                                )

                    with changes_col:
                        if st.button(
                            "Request Changes",
                            key=f"request_changes_{request_id}",
                            use_container_width=True,
                        ):
                            if len(change_reason.strip()) < 5:
                                st.warning(
                                    "Please explain the requested changes "
                                    "using at least 5 characters."
                                )
                            else:
                                changes_result = request_changes(
                                    request_id,
                                    change_reason.strip(),
                                )

                                if changes_result.get("success"):
                                    st.success(changes_result["message"])
                                    st.rerun()
                                else:
                                    st.error(
                                        changes_result.get(
                                            "error",
                                            "Could not request changes."
                                        )
                                    )

                else:
                    if st.button(
                        "Reopen & Request Changes",
                        key=f"reopen_request_{request_id}",
                        use_container_width=True,
                    ):
                        if len(change_reason.strip()) < 5:
                            st.warning(
                                "Please explain the requested changes "
                                "using at least 5 characters."
                            )
                        else:
                            changes_result = request_changes(
                                request_id,
                                change_reason.strip(),
                            )

                            if changes_result.get("success"):
                                st.success(
                                    "Request reopened. The assigned "
                                    "analyst has been notified."
                                )
                                st.rerun()
                            else:
                                st.error(
                                    changes_result.get(
                                        "error",
                                        "Could not reopen the request."
                                    )
                                )


def render_business_messages_page(profile):
    """Allow business users to communicate about their requests."""

    if profile.get("role") != "business_user":
        st.error("You do not have permission to access this page.")
        return

    st.title("Messages")
    st.write(
        "Communicate with your analytics team about your submitted requests."
    )

    # Retrieve requests visible to the current user.
    requests_result = get_my_requests()

    if not requests_result.get("success"):
        st.error(
            "Unable to retrieve your requests: "
            + requests_result.get("error", "Unknown error")
        )
        return

    requests = requests_result.get("data", [])

    if not requests:
        st.info("Submit a request before starting a conversation.")
        return

    # Select the request whose conversation the user wants to view.
    selected_request = st.selectbox(
        "Select a request",
        options=requests,
        format_func=lambda item: (
            f"#{item['request_id']} — {item.get('title', 'Untitled request')}"
        ),
        key="business_message_request",
    )

    request_id = int(selected_request["request_id"])

    st.divider()
    st.markdown(f"### Conversation for Request #{request_id}")

    # Retrieve messages for the selected request.
    messages_result = get_request_messages(request_id)

    if not messages_result.get("success"):
        st.error(
            "Unable to retrieve messages: "
            + messages_result.get("error", "Unknown error")
        )
        return

    messages = messages_result.get("messages", [])

    current_user_id = profile.get("user_id")

    if messages:
        for message in messages:

            is_own_message = (
                str(message.get("sender_id")) == str(current_user_id)
            )

            sender_label = (
                "You" if is_own_message else "Analytics Team"
            )

            chat_role = "user" if is_own_message else "assistant"

            with st.chat_message(chat_role):
                st.caption(
                    f"{sender_label} · "
                    f"{message.get('created_at', '')}"
                )

                st.write(message.get("message_body", ""))

                if message.get("new_expected_date"):
                    st.caption(
                        "Proposed delivery date: "
                        + str(message["new_expected_date"])
                    )

    else:
        st.info(
            "There are no messages for this request yet. "
            "Send a message below to start the conversation."
        )

    st.divider()
    st.markdown("### Send a message")

    with st.form(
        "business_send_message_form",
        clear_on_submit=True,
    ):
        message_body = st.text_area(
            "Your message",
            placeholder="Type your question or update here...",
            height=120,
        )

        submitted = st.form_submit_button(
            "Send Message",
            type="primary",
            use_container_width=True,
        )

    if submitted:

        if not message_body.strip():
            st.error("Please enter a message before sending.")

        else:
            with st.spinner("Sending your message..."):

                result = send_message(
                    request_id=request_id,
                    message_body=message_body,
                )

            if result.get("success"):
                st.success("Your message was sent successfully.")
                st.rerun()

            else:
                st.error(
                    "Unable to send your message: "
                    + result.get("error", "Unknown error")
                )



def render_analyst_messages_page(profile):
    """Allow analysts to communicate about their assigned requests."""

    if profile.get("role") != "analyst":
        st.error("You do not have permission to access this page.")
        return

    st.title("Messages")
    st.write(
        "Communicate with business users about your assigned requests."
    )

    # Retrieve requests visible to the authenticated analyst.
    requests_result = get_my_requests()

    if not requests_result.get("success"):
        st.error(
            "Unable to retrieve assigned requests: "
            + requests_result.get("error", "Unknown error")
        )
        return

    analyst_id = profile.get("user_id")

    requests = [
        request
        for request in requests_result.get("data", [])
        if str(request.get("assigned_to")) == str(analyst_id)
    ]

    if not requests:
        st.info("You do not currently have any assigned requests.")
        return

    # Select an assigned request.
    selected_request = st.selectbox(
        "Select a request",
        options=requests,
        format_func=lambda item: (
            f"#{item['request_id']} - "
            f"{item.get('title', 'Untitled request')}"
        ),
        key="analyst_message_request",
    )

    request_id = int(selected_request["request_id"])

    st.divider()
    st.markdown(f"### Conversation for Request #{request_id}")

    # Retrieve messages for the selected request.
    messages_result = get_request_messages(request_id)

    if not messages_result.get("success"):
        st.error(
            "Unable to retrieve messages: "
            + messages_result.get("error", "Unknown error")
        )
        return

    # Explicitly exclude private internal notes.
    messages = [
        message
        for message in messages_result.get("messages", [])
        if not message.get("is_internal", False)
    ]

    current_user_id = profile.get("user_id")

    if messages:
        for message in messages:
            is_own_message = (
                str(message.get("sender_id")) == str(current_user_id)
            )

            sender_label = (
                "You" if is_own_message else "Business User"
            )

            chat_role = "user" if is_own_message else "assistant"

            with st.chat_message(chat_role):
                st.caption(
                    f"{sender_label} | "
                    f"{message.get('created_at', '')}"
                )

                st.write(message.get("message_body", ""))

                if message.get("new_expected_date"):
                    st.caption(
                        "Proposed delivery date: "
                        + str(message["new_expected_date"])
                    )

    else:
        st.info(
            "There are no public messages for this request yet."
        )

    st.divider()
    st.markdown("### Send a message")

    with st.form(
        key=f"analyst_send_message_form_{request_id}",
        clear_on_submit=True,
    ):
        message_body = st.text_area(
            "Your message",
            placeholder="Type your response or update here...",
            height=120,
        )

        submitted = st.form_submit_button(
            "Send Message",
            type="primary",
            use_container_width=True,
        )

    if submitted:
        if not message_body.strip():
            st.warning("Please enter a message before sending.")

        else:
            with st.spinner("Sending message..."):
                result = send_message(
                    request_id=request_id,
                    message_body=message_body,
                )

            if result.get("success"):
                st.success("Your message was sent successfully.")
                st.rerun()

            else:
                st.error(
                    "Unable to send message: "
                    + result.get("error", "Unknown error")
                )



def render_analyst_deadlines_page(profile):
    """Display deadline monitoring for the current analyst."""

    st.title("Deadlines")
    st.write(
        "Monitor your assigned requests and upcoming delivery deadlines."
    )

    analyst_id = profile.get("user_id")

    if not analyst_id:
        st.error("Your analyst profile could not be identified.")
        return

    # Retrieve requests visible to the authenticated analyst.
    requests_result = get_my_requests()

    if not requests_result.get("success"):
        st.error(
            "Unable to retrieve requests: "
            + requests_result.get("error", "Unknown error")
        )
        return

    assigned_requests = [
        request
        for request in requests_result.get("data", [])
        if str(request.get("assigned_to")) == str(analyst_id)
    ]

    # Retrieve status and priority lookup information.
    priorities_result = get_priorities()
    statuses_result = get_statuses()

    for result, label in [
        (priorities_result, "priorities"),
        (statuses_result, "statuses"),
    ]:
        if not result.get("success"):
            st.error(
                f"Unable to retrieve {label}: "
                + result.get("error", "Unknown error")
            )
            return

    priority_map = {
        item["priority_id"]: item["priority_name"]
        for item in priorities_result.get("data", [])
    }

    status_map = {
        item["status_id"]: item["status_name"]
        for item in statuses_result.get("data", [])
    }

    if not assigned_requests:
        st.info("You currently have no assigned requests.")
        return

    # Exclude completed and cancelled requests from deadline monitoring.
    active_requests = [
        request
        for request in assigned_requests
        if status_map.get(request.get("status_id"))
        not in ("Closed", "Cancelled")
    ]

    eastern = ZoneInfo("America/New_York")
    today = datetime.now(eastern).date()


    overdue_count = 0
    due_soon_count = 0
    no_deadline_count = 0
    display_rows = []

    for request in active_requests:
        expected_date = request.get("expected_date")
        days_remaining = None

        if expected_date:
            try:
                deadline = datetime.strptime(
                    str(expected_date)[:10], "%Y-%m-%d"
                ).date()

                days_remaining = (deadline - today).days

            except ValueError:
                days_remaining = None

        if not expected_date or days_remaining is None:
            no_deadline_count += 1
            deadline_label = "Not set"
            deadline_status = "No deadline"

        elif days_remaining < 0:
            overdue_count += 1
            deadline_label = str(expected_date)
            deadline_status = "Overdue"

        elif days_remaining <= 7:
            due_soon_count += 1
            deadline_label = str(expected_date)
            deadline_status = (
                "Due today" if days_remaining == 0
                else f"Due in {days_remaining} days"
            )

        else:
            deadline_label = str(expected_date)
            deadline_status = f"{days_remaining} days remaining"

        display_rows.append({
            "Request ID": request.get("request_id"),
            "Title": request.get("title", ""),
            "Priority": priority_map.get(
                request.get("priority_id"), "Unknown"
            ),
            "Status": status_map.get(
                request.get("status_id"), "Unknown"
            ),
            "Expected Date": deadline_label,
            "Deadline Status": deadline_status,
        })

    # Sort dated requests first, followed by requests without deadlines.
    display_rows.sort(
        key=lambda item: (
            item["Expected Date"] == "Not set",
            item["Expected Date"],
        )
    )

    # Display deadline metrics.
    col1, col2, col3, col4 = st.columns(4)

    col1.metric("Active Requests", len(active_requests))
    col2.metric("Overdue", overdue_count)
    col3.metric("Due Within 7 Days", due_soon_count)
    col4.metric("No Deadline Set", no_deadline_count)

    st.divider()

    st.subheader("Deadline Overview")

    if display_rows:
        st.dataframe(
            display_rows,
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.success("You have no outstanding assigned requests.")

    st.divider()

    st.caption(
        "Completed and cancelled requests are excluded. "
        "Upcoming deadlines include requests due within the next seven days."
    )

def render_analyst_performance_page(profile):
    """Display performance metrics for the authenticated analyst."""

    st.title("My Performance")
    st.caption("Review your workload, completion history, and turnaround performance.")

    with st.spinner("Loading your performance metrics..."):
        result = get_analyst_performance()

    if not result.get("success"):
        st.error(
            f"Unable to load your performance report: "
            f"{result.get('error', 'Unknown error')}"
        )
        return

    data = result.get("data", {})

    # Primary workload metrics
    st.subheader("Workload Overview")

    col1, col2, col3, col4 = st.columns(4)

    col1.metric("Total Assigned", data.get("total_assigned", 0))
    col2.metric("Currently Open", data.get("open_count", 0))
    col3.metric("Completed", data.get("completed_count", 0))
    col4.metric("Overdue", data.get("overdue_count", 0))

    st.divider()

    # Completion performance
    st.subheader("Completion Performance")

    col1, col2, col3 = st.columns(3)

    on_time_rate = data.get("on_time_rate")
    average_turnaround = data.get("average_turnaround_hours")

    col1.metric(
        "On-Time Completion Rate",
        f"{on_time_rate:.1f}%" if on_time_rate is not None else "N/A",
    )

    col2.metric(
        "Completed On Time",
        data.get("on_time_count", 0),
    )

    col3.metric(
        "Completed Late",
        data.get("late_count", 0),
    )

    if on_time_rate is not None:
        st.progress(min(max(on_time_rate / 100, 0.0), 1.0))
        st.caption(
            "Percentage of completed requests with a deadline "
            "that were resolved on or before their expected date."
        )
    else:
        st.info(
            "An on-time completion rate will appear once you have "
            "completed requests with recorded deadlines."
        )

    st.divider()

    # Turnaround time
    st.subheader("Turnaround Time")

    if average_turnaround is not None:
        days = int(average_turnaround // 24)
        remaining_hours = round(average_turnaround % 24, 1)

        st.metric(
            "Average Turnaround",
            f"{average_turnaround:.2f} hours",
        )

        st.caption(
            f"Approximately {days} days and "
            f"{remaining_hours} hours from request creation to completion."
        )
    else:
        st.info(
            "Average turnaround time will appear once you have "
            "completed requests with recorded timestamps."
        )

    st.divider()

    # Additional request information
    st.subheader("Additional Request Information")

    col1, col2 = st.columns(2)

    col1.metric(
        "Cancelled Requests",
        data.get("cancelled_count", 0),
    )

    col2.metric(
        "Completed Without Deadline",
        data.get("without_deadline_count", 0),
    )

    st.caption(
        "These metrics reflect requests assigned to your analyst account. "
        "Turnaround time measures the time between request creation "
        "and resolution."
    )

    if data.get("open_count", 0) > 0:
        st.info(
            f"You currently have {data['open_count']} open request(s). "
            "Visit Assigned Requests or Deadlines to review them."
        )

# =========================================================
# ROLE PAGE ROUTING
# =========================================================


def render_manager_all_requests_page(profile):
    """Display all analytics requests to authorized managers."""

    st.title("All Requests")
    st.write(f"Welcome, **{profile['full_name']}**.")
    st.caption(
        "Review, search, and monitor analytics requests across the organization."
    )

    # Retrieve requests and lookup information.
    with st.spinner("Loading all requests..."):
        requests_result = get_all_requests()
        types_result = get_request_types()
        priorities_result = get_priorities()
        statuses_result = get_statuses()

    # Handle retrieval errors.
    for name, result in [
        ("Requests", requests_result),
        ("Request types", types_result),
        ("Priorities", priorities_result),
        ("Statuses", statuses_result),
    ]:
        if not result.get("success"):
            st.error(
                f"Unable to load {name.lower()}: "
                f"{result.get('error', 'Unknown error')}"
            )
            return

    requests = requests_result.get("data", [])
    request_types = types_result.get("data", [])
    priorities = priorities_result.get("data", [])
    statuses = statuses_result.get("data", [])

    # Create lookup dictionaries.
    type_lookup = {
        item["type_id"]: item["type_name"]
        for item in request_types
    }

    priority_lookup = {
        item["priority_id"]: item["priority_name"]
        for item in priorities
    }

    status_lookup = {
        item["status_id"]: item["status_name"]
        for item in statuses
    }

    # Display overview metrics.
    total_requests = len(requests)

    closed_ids = {
        item["status_id"]
        for item in statuses
        if item["status_name"].lower() == "closed"
    }

    cancelled_ids = {
        item["status_id"]
        for item in statuses
        if item["status_name"].lower() == "cancelled"
    }

    completed_or_cancelled = closed_ids | cancelled_ids

    open_requests = [
        request for request in requests
        if request.get("status_id") not in completed_or_cancelled
    ]

    overdue_requests = [
        request for request in open_requests
        if request.get("is_overdue")
    ]

    col1, col2, col3, col4 = st.columns(4)

    col1.metric("Total Requests", total_requests)
    col2.metric("Open Requests", len(open_requests))
    col3.metric("Overdue Requests", len(overdue_requests))
    col4.metric(
        "Completed Requests",
        sum(
            1 for request in requests
            if request.get("status_id") in closed_ids
        ),
    )

    st.divider()

    # Search and filtering controls.
    st.markdown("### Search and Filter")

    col1, col2 = st.columns(2)

    with col1:
        search_term = st.text_input(
            "Search requests",
            placeholder="Search by title, requester, analyst, or ID...",
            key="manager_all_requests_search",
        )

    with col2:
        status_options = ["All"] + [
            item["status_name"] for item in statuses
        ]

        selected_status = st.selectbox(
            "Filter by Status",
            status_options,
            key="manager_all_requests_status",
        )

    col3, col4 = st.columns(2)

    with col3:
        priority_options = ["All"] + [
            item["priority_name"] for item in priorities
        ]

        selected_priority = st.selectbox(
            "Filter by Priority",
            priority_options,
            key="manager_all_requests_priority",
        )

    with col4:
        type_options = ["All"] + [
            item["type_name"] for item in request_types
        ]

        selected_type = st.selectbox(
            "Filter by Request Type",
            type_options,
            key="manager_all_requests_type",
        )

    # Apply filters.
    filtered_requests = []

    for request in requests:
        status_name = status_lookup.get(
            request.get("status_id"), "Unknown"
        )

        priority_name = priority_lookup.get(
            request.get("priority_id"), "Unknown"
        )

        type_name = type_lookup.get(
            request.get("type_id"), "Unknown"
        )

        if selected_status != "All" and status_name != selected_status:
            continue

        if selected_priority != "All" and priority_name != selected_priority:
            continue

        if selected_type != "All" and type_name != selected_type:
            continue

        searchable_text = " ".join([
            str(request.get("request_id", "")),
            str(request.get("title", "")),
            str(request.get("requester_name", "")),
            str(request.get("requester_email", "")),
            str(request.get("analyst_name", "")),
        ]).lower()

        if search_term.strip().lower() not in searchable_text:
            continue

        filtered_requests.append(request)

    st.divider()

    st.markdown("### Request Directory")

    st.caption(
        f"Showing {len(filtered_requests)} of {total_requests} requests."
    )

    if not filtered_requests:
        st.info("No requests match the selected search and filters.")
        return

    # Prepare readable table data.
    table_data = []

    for request in filtered_requests:
        table_data.append({
            "Request ID": request.get("request_id"),
            "Title": request.get("title"),
            "Requester": request.get("requester_name"),
            "Assigned Analyst": request.get("analyst_name"),
            "Request Type": type_lookup.get(
                request.get("type_id"), "Unknown"
            ),
            "Priority": priority_lookup.get(
                request.get("priority_id"), "Unknown"
            ),
            "Status": status_lookup.get(
                request.get("status_id"), "Unknown"
            ),
            "Needed Date": str(
                request.get("needed_date") or "Not specified"
            )[:10],
            "Expected Date": str(
                request.get("expected_date") or "Not determined"
            )[:10],
            "Overdue": (
                "Yes" if request.get("is_overdue") else "No"
            ),
        })

    st.dataframe(
        table_data,
        use_container_width=True,
        hide_index=True,
    )

    # Individual request details.
    st.divider()
    st.markdown("### Request Details")

    selected_request_id = st.selectbox(
        "Select a request to view its details",
        options=[
            request["request_id"]
            for request in filtered_requests
        ],
        format_func=lambda request_id: (
            f"#{request_id} - "
            + next(
                (
                    request.get("title", "Untitled")
                    for request in filtered_requests
                    if request["request_id"] == request_id
                ),
                "Untitled",
            )
        ),
        key="manager_all_requests_detail",
    )

    selected_request = next(
        (
            request for request in filtered_requests
            if request["request_id"] == selected_request_id
        ),
        None,
    )

    if selected_request:
        with st.container(border=True):
            st.subheader(
                f"Request #{selected_request['request_id']}: "
                f"{selected_request.get('title', 'Untitled')}"
            )

            detail_col1, detail_col2 = st.columns(2)

            with detail_col1:
                st.write(
                    f"**Requester:** "
                    f"{selected_request.get('requester_name', 'Unknown')}"
                )
                st.write(
                    f"**Requester Email:** "
                    f"{selected_request.get('requester_email', 'Unavailable')}"
                )
                st.write(
                    f"**Assigned Analyst:** "
                    f"{selected_request.get('analyst_name', 'Unassigned')}"
                )
                st.write(
                    f"**Request Type:** "
                    f"{type_lookup.get(selected_request.get('type_id'), 'Unknown')}"
                )

            with detail_col2:
                st.write(
                    f"**Priority:** "
                    f"{priority_lookup.get(selected_request.get('priority_id'), 'Unknown')}"
                )
                st.write(
                    f"**Status:** "
                    f"{status_lookup.get(selected_request.get('status_id'), 'Unknown')}"
                )
                st.write(
                    f"**Needed Date:** "
                    f"{selected_request.get('needed_date') or 'Not specified'}"
                )
                st.write(
                    f"**Expected Date:** "
                    f"{selected_request.get('expected_date') or 'Not determined'}"
                )

            st.markdown("**Description**")

            st.write(
                selected_request.get("description")
                or "No description provided."
            )

            st.caption(
                f"Created: {selected_request.get('created_at', 'Unknown')}"
            )


def render_manager_assignments_page(profile):
    """Allow analytics managers to assign and reassign requests."""

    st.title("Request Assignments")
    st.caption(
        "Assign unassigned requests or reassign existing requests "
        "to active analysts."
    )

    # Retrieve requests, analysts, and workload information.
    with st.spinner("Loading assignment information..."):
        requests_result = get_all_requests()
        analysts_result = get_analysts()
        workload_result = get_analyst_workload()

    if not requests_result.get("success"):
        st.error(
            f"Unable to retrieve requests: "
            f"{requests_result.get('error', 'Unknown error')}"
        )
        return

    if not analysts_result.get("success"):
        st.error(
            f"Unable to retrieve analysts: "
            f"{analysts_result.get('error', 'Unknown error')}"
        )
        return

    requests = requests_result.get("data", [])
    analysts = analysts_result.get("analysts", [])

    if not analysts:
        st.warning("There are currently no active analysts available.")
        return

    # Build lookup dictionaries.
    status_result = get_statuses()
    priority_result = get_priorities()
    type_result = get_request_types()

    if not all(
        result.get("success")
        for result in [status_result, priority_result, type_result]
    ):
        st.error("Unable to retrieve request lookup information.")
        return

    status_lookup = {
        item["status_id"]: item["status_name"]
        for item in status_result["data"]
    }

    priority_lookup = {
        item["priority_id"]: item["priority_name"]
        for item in priority_result["data"]
    }

    type_lookup = {
        item["type_id"]: item["type_name"]
        for item in type_result["data"]
    }

    analyst_lookup = {
        analyst["user_id"]: analyst["full_name"]
        for analyst in analysts
    }

    # Identify closed and cancelled requests.
    inactive_status_ids = {
        item["status_id"]
        for item in status_result["data"]
        if item["status_name"].lower() in ["closed", "cancelled"]
    }

    active_requests = [
        request for request in requests
        if request.get("status_id") not in inactive_status_ids
    ]

    unassigned_requests = [
        request for request in active_requests
        if not request.get("assigned_to")
    ]

    assigned_requests = [
        request for request in active_requests
        if request.get("assigned_to")
    ]

    # Overview metrics.
    col1, col2, col3 = st.columns(3)

    col1.metric("Active Requests", len(active_requests))
    col2.metric("Unassigned Requests", len(unassigned_requests))
    col3.metric("Assigned Requests", len(assigned_requests))

    st.divider()

    # Analyst workload.
    st.markdown("### Analyst Availability")

    if workload_result.get("success"):
        workload = workload_result.get("data", [])

        workload_table = []

        for analyst in analysts:
            analyst_workload = next(
                (
                    item for item in workload
                    if item.get("user_id") == analyst["user_id"]
                ),
                {},
            )

            workload_table.append({
                "Analyst": analyst["full_name"],
                "Open Requests": analyst_workload.get(
                    "open_requests", 0
                ),
                "Load Score": analyst_workload.get(
                    "load_score", 0
                ),
            })

        st.dataframe(
            workload_table,
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.warning(
            "Analyst workload information is temporarily unavailable."
        )

    st.divider()

    # Current request assignments.
    st.markdown("### Current Assignments")

    if active_requests:
        assignment_table = []

        for request in active_requests:
            assignment_table.append({
                "Request ID": request["request_id"],
                "Title": request.get("title"),
                "Requester": request.get("requester_name"),
                "Assigned Analyst": analyst_lookup.get(
                    request.get("assigned_to"),
                    "Unassigned",
                ),
                "Request Type": type_lookup.get(
                    request.get("type_id"), "Unknown"
                ),
                "Priority": priority_lookup.get(
                    request.get("priority_id"), "Unknown"
                ),
                "Status": status_lookup.get(
                    request.get("status_id"), "Unknown"
                ),
                "Expected Date": str(
                    request.get("expected_date") or "Not determined"
                )[:10],
            })

        st.dataframe(
            assignment_table,
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("There are no active requests to assign.")

    st.divider()

    # Assignment form.
    st.markdown("### Assign or Reassign a Request")

    if not active_requests:
        st.info("No active requests are available for assignment.")
        return

    request_options = [
        request["request_id"]
        for request in active_requests
    ]

    selected_request_id = st.selectbox(
        "Select Request",
        options=request_options,
        format_func=lambda request_id: (
            f"#{request_id} - "
            + next(
                (
                    request.get("title", "Untitled")
                    for request in active_requests
                    if request["request_id"] == request_id
                ),
                "Untitled",
            )
        ),
        key="manager_assignment_request",
    )

    selected_request = next(
        request for request in active_requests
        if request["request_id"] == selected_request_id
    )

    current_analyst_id = selected_request.get("assigned_to")

    current_analyst_name = analyst_lookup.get(
        current_analyst_id,
        "Unassigned",
    )

    st.write(
        f"**Current Assignment:** {current_analyst_name}"
    )

    analyst_options = [
        analyst["user_id"]
        for analyst in analysts
    ]

    default_analyst_index = (
        analyst_options.index(current_analyst_id)
        if current_analyst_id in analyst_options
        else 0
    )

    with st.form("manager_assignment_form"):
        selected_analyst_id = st.selectbox(
            "Assign to Analyst",
            options=analyst_options,
            index=default_analyst_index,
            format_func=lambda analyst_id: analyst_lookup.get(
                analyst_id, "Unknown Analyst"
            ),
        )

        submitted = st.form_submit_button(
            "Save Assignment",
            type="primary",
            use_container_width=True,
        )

        if submitted:
            if selected_analyst_id == current_analyst_id:
                st.info(
                    "This request is already assigned to the selected analyst."
                )
            else:
                with st.spinner("Saving assignment..."):
                    result = assign_request(
                        request_id=selected_request_id,
                        analyst_id=selected_analyst_id,
                    )

                if result.get("success"):
                    st.success(result.get(
                        "message",
                        "Request assigned successfully.",
                    ))

                    notification = result.get("notification", {})

                    if notification.get("success"):
                        st.success(
                            notification.get(
                                "message",
                                "Requester notification sent.",
                            )
                        )
                    else:
                        st.warning(
                            notification.get(
                                "message",
                                "Assignment succeeded, but notification failed.",
                            )
                        )

                    st.rerun()

                else:
                    st.error(
                        f"Assignment failed: "
                        f"{result.get('error', 'Unknown error')}"
                    )


def render_manager_team_workload_page(profile):
    """Display team workload information to analytics managers."""

    st.title("Team Workload")
    st.caption(
        "Monitor open requests and workload distribution across analysts."
    )

    with st.spinner("Loading team workload..."):
        result = get_analyst_workload()

    if not result.get("success"):
        st.error(
            f"Unable to load team workload: "
            f"{result.get('message', result.get('error', 'Unknown error'))}"
        )
        return

    workload = result.get("data", [])

    if not workload:
        st.info("No analyst workload information is currently available.")
        return

    # Calculate team metrics.
    total_open = sum(
        item.get("open_requests", 0)
        for item in workload
    )

    analyst_count = len(workload)

    average_load = (
        total_open / analyst_count
        if analyst_count else 0
    )

    highest_load = max(
        workload,
        key=lambda item: item.get("open_requests", 0),
    )

    # Summary metrics.
    col1, col2, col3 = st.columns(3)

    col1.metric("Active Analysts", analyst_count)
    col2.metric("Total Open Requests", total_open)
    col3.metric("Average Requests per Analyst", f"{average_load:.1f}")

    st.divider()

    st.markdown("### Analyst Workload Overview")

    table_data = []

    for analyst in workload:
        table_data.append({
            "Analyst": analyst.get("full_name", "Unknown"),
            "Open Requests": analyst.get("open_requests", 0),
            "Load Score": analyst.get("load_score", 0),
        })

    st.dataframe(
        table_data,
        use_container_width=True,
        hide_index=True,
    )

    st.divider()

    st.markdown("### Individual Analyst Workloads")

    columns = st.columns(min(3, analyst_count))

    for index, analyst in enumerate(workload):
        with columns[index % len(columns)]:
            open_count = analyst.get("open_requests", 0)

            st.markdown(
                f"**{analyst.get('full_name', 'Unknown Analyst')}**"
            )

            st.metric("Open Requests", open_count)

            st.progress(min(open_count / 6, 1.0))

            st.caption(
                f"{max(0, 6 - open_count)} of 6 request slots remaining"
            )

    st.divider()

    st.markdown("### Workload Monitoring")

    st.info(
        f"Highest current workload: "
        f"**{highest_load.get('full_name', 'Unknown')}** "
        f"with **{highest_load.get('open_requests', 0)}** open requests."
    )

    if any(
        item.get("open_requests", 0) >= 6
        for item in workload
    ):
        st.warning(
            "At least one analyst has reached the configured "
            "six-open-request limit."
        )
    else:
        st.success(
            "No analyst has reached the configured "
            "six-open-request limit."
        )


def render_manager_overdue_requests_page(profile):
    """Display overdue requests to analytics managers."""

    st.title("Overdue Requests")
    st.caption(
        "Monitor requests that have passed their expected completion dates."
    )

    with st.spinner("Loading overdue requests..."):
        result = get_overdue_requests()

    if not result.get("success"):
        st.error(
            f"Unable to load overdue requests: "
            f"{result.get('message', result.get('error', 'Unknown error'))}"
        )
        return

    overdue_requests = result.get("data", [])

    # Summary metrics.
    total_overdue = len(overdue_requests)

    most_overdue = max(
        overdue_requests,
        key=lambda item: item.get("days_late") or 0,
        default=None,
    )

    high_priority_count = sum(
        1
        for item in overdue_requests
        if (item.get("priority_name") or "").lower()
        in ("high", "urgent")
    )

    col1, col2, col3 = st.columns(3)

    col1.metric("Total Overdue Requests", total_overdue)

    col2.metric(
        "Most Days Overdue",
        most_overdue.get("days_late", 0) if most_overdue else 0,
    )

    col3.metric(
        "High / Urgent Priority",
        high_priority_count,
    )

    st.divider()

    if not overdue_requests:
        st.success("There are currently no overdue requests.")
        st.info(
            "Requests will appear here automatically when they pass "
            "their expected completion dates."
        )
        return

    st.markdown("### Overdue Request Monitoring")

    # Search and priority filters.
    search_col, priority_col = st.columns([2, 1])

    with search_col:
        search_term = st.text_input(
            "Search requests",
            placeholder="Search by request ID, title, or analyst...",
            key="manager_overdue_search",
        )

    priorities = sorted({
        item.get("priority_name", "Unknown")
        for item in overdue_requests
    })

    with priority_col:
        selected_priority = st.selectbox(
            "Filter by priority",
            ["All Priorities"] + priorities,
            key="manager_overdue_priority",
        )

    filtered_requests = overdue_requests.copy()

    if selected_priority != "All Priorities":
        filtered_requests = [
            item
            for item in filtered_requests
            if item.get("priority_name") == selected_priority
        ]

    if search_term:
        search_lower = search_term.lower()

        filtered_requests = [
            item
            for item in filtered_requests
            if (
                search_lower in str(item.get("request_id", "")).lower()
                or search_lower in str(item.get("title", "")).lower()
                or search_lower in str(item.get("analyst", "")).lower()
            )
        ]

    # Display the most overdue requests first.
    filtered_requests.sort(
        key=lambda item: item.get("days_late") or 0,
        reverse=True,
    )

    st.caption(
        f"Showing {len(filtered_requests)} of {total_overdue} overdue requests."
    )

    if not filtered_requests:
        st.info("No overdue requests match your current filters.")
        return

    table_data = []

    for request in filtered_requests:
        table_data.append({
            "Request ID": request.get("request_id"),
            "Request Title": request.get("title", "Untitled"),
            "Priority": request.get("priority_name", "Unknown"),
            "Assigned Analyst": request.get("analyst", "Unassigned"),
            "Expected Date": request.get("expected_date"),
            "Days Overdue": request.get("days_late", 0),
        })

    st.dataframe(
        table_data,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Days Overdue": st.column_config.NumberColumn(
                "Days Overdue",
                format="%d days",
            ),
        },
    )


def render_manager_analytics_page(profile):
    """Display analytics and historical performance reporting."""

    st.title("Analytics")
    st.caption(
        "Explore request demand, team performance, completion efficiency, "
        "and historical trends."
    )

    # Retrieve analytics data.
    with st.spinner("Loading analytics reports..."):
        workload_result = get_analyst_workload()
        turnaround_result = get_turnaround_by_type()
        overdue_result = get_overdue_requests()
        volume_result = get_request_volume_by_department_and_type()
        snapshots_result = get_analyst_performance_snapshots()
        completion_result = get_completion_performance()

    # Handle individual service errors without hiding other reports.
    results = {
        "Analyst workload": workload_result,
        "Turnaround": turnaround_result,
        "Overdue requests": overdue_result,
        "Request volume": volume_result,
        "Performance snapshots": snapshots_result,
        "Completion performance": completion_result,
    }

    for report_name, result in results.items():
        if not result.get("success"):
            st.warning(
                f"{report_name} could not be loaded: "
                f"{result.get('message', result.get('error', 'Unknown error'))}"
            )

    workload = (
        workload_result.get("data", [])
        if workload_result.get("success") else []
    )

    turnaround = (
        turnaround_result.get("data", [])
        if turnaround_result.get("success") else []
    )

    overdue = (
        overdue_result.get("data", [])
        if overdue_result.get("success") else []
    )

    volume = (
        volume_result.get("data", [])
        if volume_result.get("success") else []
    )

    snapshots = (
        snapshots_result.get("data", [])
        if snapshots_result.get("success") else []
    )

    completion = (
        completion_result.get("data", {})
        if completion_result.get("success") else {}
    )

    # -----------------------------------------------------
    # PERFORMANCE OVERVIEW
    # -----------------------------------------------------

    st.markdown("### Performance Overview")

    total_completed = completion.get("total_completed", 0)
    on_time_rate = completion.get("on_time_rate")
    overdue_count = len(overdue)
    analyst_count = len(workload)

    col1, col2, col3, col4 = st.columns(4)

    col1.metric(
        "Active Analysts",
        analyst_count,
    )

    col2.metric(
        "Completed Requests",
        total_completed,
    )

    col3.metric(
        "On-Time Completion",
        f"{on_time_rate:.1f}%" if on_time_rate is not None else "N/A",
    )

    col4.metric(
        "Overdue Requests",
        overdue_count,
    )

    st.divider()

    # -----------------------------------------------------
    # REQUEST DEMAND
    # -----------------------------------------------------

    st.markdown("### Request Demand")

    if volume:
        request_type_totals = {}

        for item in volume:
            request_type = item.get("type_name", "Unknown")
            count = item.get("request_count", 0)

            request_type_totals[request_type] = (
                request_type_totals.get(request_type, 0) + count
            )

        demand_col1, demand_col2 = st.columns(2)

        with demand_col1:
            st.markdown("#### Requests by Type")

            chart_data = [
                {
                    "Request Type": name,
                    "Request Count": count,
                }
                for name, count in request_type_totals.items()
            ]

            st.bar_chart(
                chart_data,
                x="Request Type",
                y="Request Count",
            )

        with demand_col2:
            st.markdown("#### Department and Request Type")

            st.dataframe(
                [
                    {
                        "Department": item.get(
                            "department_name", "Unknown"
                        ),
                        "Request Type": item.get(
                            "type_name", "Unknown"
                        ),
                        "Request Count": item.get("request_count", 0),
                    }
                    for item in volume
                ],
                use_container_width=True,
                hide_index=True,
            )
    else:
        st.info("No request-volume data is currently available.")

    st.divider()

    # -----------------------------------------------------
    # ANALYST WORKLOAD
    # -----------------------------------------------------

    st.markdown("### Analyst Workload")

    if workload:
        workload_chart = [
            {
                "Analyst": item.get("full_name", "Unknown"),
                "Open Requests": item.get("open_requests", 0),
            }
            for item in workload
        ]

        st.bar_chart(
            workload_chart,
            x="Analyst",
            y="Open Requests",
        )

        st.dataframe(
            [
                {
                    "Analyst": item.get("full_name", "Unknown"),
                    "Open Requests": item.get("open_requests", 0),
                    "Load Score": item.get("load_score", 0),
                }
                for item in workload
            ],
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("No analyst workload data is currently available.")

    st.divider()

    # -----------------------------------------------------
    # TURNAROUND PERFORMANCE
    # -----------------------------------------------------

    st.markdown("### Average Turnaround by Request Type")

    if turnaround:
        st.dataframe(
            turnaround,
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info(
            "Turnaround metrics will appear after requests have "
            "been completed and recorded."
        )

    st.divider()

    # -----------------------------------------------------
    # COMPLETION PERFORMANCE
    # -----------------------------------------------------

    st.markdown("### Completion Performance")

    if completion_result.get("success"):
        completion_col1, completion_col2, completion_col3 = (
            st.columns(3)
        )

        completion_col1.metric(
            "Completed On Time",
            completion.get("on_time", 0),
        )

        completion_col2.metric(
            "Completed Late",
            completion.get("overdue", 0),
        )

        completion_col3.metric(
            "Without Expected Date",
            completion.get("without_expected_date", 0),
        )

        completion_chart = [
            {
                "Completion Outcome": "On Time",
                "Requests": completion.get("on_time", 0),
            },
            {
                "Completion Outcome": "Late",
                "Requests": completion.get("overdue", 0),
            },
            {
                "Completion Outcome": "No Expected Date",
                "Requests": completion.get("without_expected_date", 0),
            },
        ]

        if total_completed > 0:
            st.bar_chart(
                completion_chart,
                x="Completion Outcome",
                y="Requests",
            )
        else:
            st.info(
                "Completion charts will become available "
                "when requests are closed."
            )

    st.divider()

    # -----------------------------------------------------
    # HISTORICAL PERFORMANCE SNAPSHOTS
    # -----------------------------------------------------

    st.markdown("### Historical Analyst Performance")

    if snapshots:
        snapshot_totals = {}

        for item in snapshots:
            snapshot_date = str(item.get("snapshot_date", "Unknown"))

            if snapshot_date not in snapshot_totals:
                snapshot_totals[snapshot_date] = {
                    "Snapshot Date": snapshot_date,
                    "Open Requests": 0,
                    "Closed Requests": 0,
                    "Overdue Requests": 0,
                }

            snapshot_totals[snapshot_date]["Open Requests"] += (
                item.get("open_count", 0) or 0
            )

            snapshot_totals[snapshot_date]["Closed Requests"] += (
                item.get("closed_count", 0) or 0
            )

            snapshot_totals[snapshot_date]["Overdue Requests"] += (
                item.get("overdue_count", 0) or 0
            )

        historical_data = sorted(
            snapshot_totals.values(),
            key=lambda item: item["Snapshot Date"],
        )

        st.line_chart(
            historical_data,
            x="Snapshot Date",
            y=[
                "Open Requests",
                "Closed Requests",
                "Overdue Requests",
            ],
        )

        st.caption(
            "Historical totals combine the daily snapshots "
            "of all active analysts."
        )
    else:
        st.info(
            "No historical snapshots are available yet. "
            "Generate daily snapshots from the Manager Dashboard."
        )

    st.divider()

    # -----------------------------------------------------
    # OVERDUE REQUEST SUMMARY
    # -----------------------------------------------------

    st.markdown("### Overdue Request Details")

    if overdue:
        st.dataframe(
            [
                {
                    "Request ID": item.get("request_id"),
                    "Request Title": item.get("title", "Untitled"),
                    "Priority": item.get("priority_name", "Unknown"),
                    "Assigned Analyst": item.get("analyst", "Unassigned"),
                    "Expected Date": item.get("expected_date"),
                    "Days Overdue": item.get("days_late", 0),
                }
                for item in overdue
            ],
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.success("There are currently no overdue requests.")

    st.caption(
        "Analytics data is retrieved from the portal's reporting "
        "services and Supabase reporting views."
    )


def render_selected_section(profile):
    role = profile["role"]
    section = st.session_state["dashboard_section"]

    if section == "dashboard":
        if role == "business_user":
            render_business_dashboard(profile)
        elif role == "analyst":
            render_analyst_dashboard(profile)
        elif role == "analytics_manager":
            render_manager_dashboard(profile)

        return

    page_titles = {
        "submit_request": "Submit an Analytics Request",
        "my_requests": "My Requests",
        "messages": "Messages",
        "assigned_requests": "Assigned Requests",
        "deadlines": "Deadlines",
        "performance": "Performance",
        "all_requests": "All Requests",
        "assignments": "Request Assignments",
        "team_workload": "Team Workload",
        "overdue_requests": "Overdue Requests",
        "analytics": "Analytics",
        "user_management": "User Management",
    }

    allowed_sections = {
        item[1] for item in ROLE_NAVIGATION[role]
    }

    if section not in allowed_sections:
        st.error("You do not have access to this page.")
        return

    if section == "submit_request":
        render_submit_request_page(profile)
        return

    if section == "my_requests":
        render_my_requests_page(profile)
        return

    if section == "assigned_requests" and role in ("analyst", "analytics_manager"):
        render_assigned_requests_page(profile)
        return

    if section == "deadlines" and role == "analyst":
        render_analyst_deadlines_page(profile)
        return

    if section == "performance" and role == "analyst":
        render_analyst_performance_page(profile)
        return

    if section == "messages" and role == "business_user":
        render_business_messages_page(profile)
        return

    if section == "messages" and role == "analyst":
        render_analyst_messages_page(profile)
        return

    if section == "all_requests" and role == "analytics_manager":
        render_manager_all_requests_page(profile)
        return

    if section == "assignments" and role == "analytics_manager":
        render_manager_assignments_page(profile)
        return

    if section == "team_workload" and role == "analytics_manager":
        render_manager_team_workload_page(profile)
        return

    if section == "overdue_requests" and role == "analytics_manager":
        render_manager_overdue_requests_page(profile)
        return

    if section == "analytics" and role == "analytics_manager":
        render_manager_analytics_page(profile)
        return

    if section == "user_management" and role == "analytics_manager":
        render_user_management_page(profile)
        return

    st.title(page_titles.get(section, "Portal"))

    st.info(
        "This page is part of the application navigation. "
        "Its backend-connected functionality is the next implementation task."
    )


def render_user_management_page(profile):
    """Allow analytics managers to manage business-user and analyst roles."""

    if profile.get("role") != "analytics_manager":
        st.error("You do not have permission to manage users.")
        return

    st.title("User Management")
    st.write(
        "Promote business users to analytics analysts or return analysts "
        "to business-user access."
    )

    result = get_user_management_data()

    if not result.get("success"):
        st.error(
            f"Unable to load user management data: {result.get('error')}"
        )
        return

    users = result.get("users", [])
    history = result.get("history", [])

    # ---------------------------------------------------------
    # ACTIVE USERS
    # ---------------------------------------------------------

    st.markdown("### Active Portal Users")

    if users:
        user_display = [
            {
                "User ID": user["user_id"],
                "Name": user["full_name"],
                "Email": user["email"],
                "Role": ROLE_TITLES.get(user["role"], user["role"]),
                "Status": "Active",
            }
            for user in users
        ]

        st.dataframe(
            user_display,
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("No active users were found.")

    st.divider()

    # ---------------------------------------------------------
    # CHANGE USER ROLE
    # ---------------------------------------------------------

    st.markdown("### Change User Role")

    eligible_users = [
        user
        for user in users
        if user["role"] in ("business_user", "analyst")
    ]

    if not eligible_users:
        st.info("There are no eligible users to promote or demote.")

    else:
        # Use user IDs as the actual selection values.
        # This prevents duplicate names or emails from causing
        # the wrong user record to be selected.
        users_by_id = {
            str(user["user_id"]): user
            for user in eligible_users
        }

        # IMPORTANT: Keep this selectbox OUTSIDE the form.
        # Changing the selection now triggers a Streamlit rerun.
        selected_user_id = st.selectbox(
            "Select a user",
            options=list(users_by_id.keys()),
            format_func=lambda user_id: (
                f"{users_by_id[user_id]['full_name']} "
                f"({users_by_id[user_id]['email']}) — "
                f"{ROLE_TITLES.get(users_by_id[user_id]['role'], users_by_id[user_id]['role'])}"
            ),
            key="user_management_selected_id",
        )

        # Retrieve the selected user's actual database record.
        selected_user = users_by_id[selected_user_id]

        current_role = selected_user["role"]

        # Determine the new role dynamically.
        new_role = (
            "analyst"
            if current_role == "business_user"
            else "business_user"
        )

        action_label = (
            "Promote to Analytics Analyst"
            if new_role == "analyst"
            else "Demote to Business User"
        )

        # Display the selected user's information.
        st.markdown("#### Selected User")

        st.write(f"**User ID:** {selected_user['user_id']}")

        st.write(
            f"**Current role:** "
            f"{ROLE_TITLES.get(current_role, current_role)}"
        )

        st.write(
            f"**New role:** "
            f"{ROLE_TITLES.get(new_role, new_role)}"
        )

        st.divider()

        # Only the confirmation and submission controls
        # belong inside the form.
        with st.form("user_role_management_form"):

            reason = st.text_input(
                "Reason for role change (optional)",
                max_chars=500,
            )

            confirmed = st.checkbox(
                f"I confirm that I want to "
                f"{action_label.lower()} "
                f"{selected_user['full_name']}."
            )

            submitted = st.form_submit_button(
                action_label,
                type="primary",
                use_container_width=True,
            )

        # -----------------------------------------------------
        # PROCESS ROLE CHANGE
        # -----------------------------------------------------

        if submitted:

            if not confirmed:
                st.warning(
                    "Please confirm the role change first."
                )

            else:
                with st.spinner("Updating user role..."):

                    change_result = change_user_role(
                        target_user_id=selected_user["user_id"],
                        new_role=new_role,
                        reason=reason.strip() or None,
                    )

                if change_result.get("success"):
                    st.success(change_result["message"])
                    st.rerun()

                else:
                    st.error(
                        f"Role change failed: "
                        f"{change_result.get('error')}"
                    )

    st.divider()

    # ---------------------------------------------------------
    # ROLE CHANGE HISTORY
    # ---------------------------------------------------------

    st.markdown("### Recent Role Change History")

    if history:
        history_display = [
            {
                "User": record["target_user_name"],
                "Changed By": record["manager_name"],
                "Previous Role": ROLE_TITLES.get(
                    record["old_role"],
                    record["old_role"],
                ),
                "New Role": ROLE_TITLES.get(
                    record["new_role"],
                    record["new_role"],
                ),
                "Reason": record.get("reason") or "Not provided",
                "Changed At": record["changed_at"],
            }
            for record in history
        ]

        st.dataframe(
            history_display,
            use_container_width=True,
            hide_index=True,
        )

    else:
        st.info("No role changes have been recorded yet.")



# =========================================================
# AUTHENTICATED APPLICATION
# =========================================================

def render_authenticated_app():
    profile_result = get_current_profile()

    if not profile_result.get("success", False):
        clear_local_authentication()

        st.warning(
            "Your session has expired or could not be validated. "
            "Please sign in again."
        )

        if st.button("Return to login", type="primary"):
            navigate_to("login")
            st.rerun()

        return

    profile = profile_result["profile"]
    role = profile.get("role")

    if role not in ROLE_NAVIGATION:
        clear_local_authentication()
        st.error("Your account does not have an authorized portal role.")
        return

    st.session_state["authenticated_profile"] = profile

    allowed_sections = {
        item[1] for item in ROLE_NAVIGATION[role]
    }

    if st.session_state["dashboard_section"] not in allowed_sections:
        st.session_state["dashboard_section"] = "dashboard"

    render_authenticated_navbar(profile)
    render_selected_section(profile)


# =========================================================
# APPLICATION ENTRY POINT
# =========================================================

def main():
    logout_message = st.session_state.pop("logout_message", None)

    if logout_message:
        st.info(logout_message)

    if st.session_state.get("authenticated_profile") is not None:
        render_authenticated_app()
        return

    if st.session_state["page"] == "login":
        render_login_page()
    else:
        render_landing_page()


if __name__ == "__main__":
    main()
