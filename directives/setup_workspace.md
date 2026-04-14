# Directive: Setup Workspace

This directive outlines the process for initializing a new Decisive workspace from scratch using the 3-layer architecture. This process ensures that the environment is consistent and reproducible.

## Goal
The goal is to replicate the entire Decisive application structure, including the backend, frontend, and automation layers, starting from an empty directory.

## Steps

### 1. Initialize Core Structure
Begin by setting up the necessary directory layers for the 3-layer architecture. This includes folders for directives, execution scripts, and temporary files.
- **Tool**: `execution/init_dirs.py`

### 2. Backend Setup
Initialize the Django-based backend. This step handles installing the necessary Python packages and creating the core Django project and initial applications (`decisions`, `waitlist`).
- **Tool**: `execution/setup_backend.py`

### 3. Frontend Setup
Initialize the Next.js frontend application. This step uses `create-next-app` to scaffold the project and installs additional UI libraries like Framer Motion and Lucide React.
- **Tool**: `execution/setup_frontend.py`

### 4. Configuration and Environment
Generate the necessary configuration files for the project to run correctly.
- **Note**: Ensure `DJANGO_SECRET_KEY` is set in your `.env` after running step 2.
- **Tool**: `execution/setup_configs.py`

## Running the Workspace
Once initialized, you can start the development servers:
- **Backend**: Navigate to `backend/` and run `python manage.py runserver`.
- **Frontend**: Navigate to `frontend/` and run `npm run dev`.
