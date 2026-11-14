# Analytics Request Portal

A Business Information Technology capstone project developed to centralize and streamline analytics request management.

The application connects business users, analysts, and analytics managers through a structured request workflow.

## Key Features

- Role-based authentication and access control
- Analytics request submission and automatic assignment
- Priority-based routing, including urgent manager assignments
- Request tracking and status history
- Analyst and manager work management
- Secure deliverable uploads and downloads
- Requester completion confirmation and revision requests
- In-app and email notifications
- Management dashboards and workload visibility

## Technology Stack

- Python 3.12
- Streamlit
- Supabase PostgreSQL
- Supabase Auth
- PostgreSQL Row Level Security
- Supabase Storage
- Pandas
- Resend
- Git and GitHub

## User Roles

**Business Users**
- Submit and track requests
- Review deliverables
- Confirm completion or request changes

**Analysts**
- Manage assigned requests
- Upload deliverables
- Submit work for review
- Complete requests with or without file uploads

**Analytics Managers**
- Oversee requests
- Receive urgent assignments
- Complete assigned requests
- Manage deliverable and review workflows

## Local Setup

1. Install Python 3.12.
2. Clone this repository.
3. Create and activate a virtual environment.
4. Install dependencies:

   `pip install -r requirements.txt`

5. Create a `.env` file using `.env.example` as a template.
6. Configure the required Supabase and Resend credentials.
7. Start the application:

   `streamlit run app.py`

## Security

- Supabase Auth handles authentication.
- PostgreSQL Row Level Security protects database records.
- Deliverables are stored in a private Supabase Storage bucket.
- Service-role credentials are reserved for trusted backend operations.
- Environment files and secrets are excluded from version control.

## Academic Project

Developed as a Business Information Technology capstone project at Polk State College.