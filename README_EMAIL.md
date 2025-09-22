# Email & Completion Links

## SMTP (optional)
Fill SMTP settings under **Integrations**:
- SMTP Host, Port
- SMTP Username, Password
- From (email)

Use **Send Test Email** to verify.

## Task completion links
- Set **App Base URL** (e.g., `https://your-streamlit-app.streamlit.app`).
- Each task shows a link like: `?complete_task=<token>`.
- When the assignee clicks it, the task is marked **Done** and a webhook is posted to UpCoach (if configured).
