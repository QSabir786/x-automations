# x_automations

This repository contains a Streamlit application for scheduling posts. It includes a Python script (`post_scheduler.py`) to manage the scheduling logic and a JSON file (`scheduled_posts.json`) to store the scheduled posts.

## Files

- `streamlit_app.py`: The main Streamlit application.
- `post_scheduler.py`: Contains the logic for scheduling posts.
- `scheduled_posts.json`: Stores the data for scheduled posts.
- `requirements.txt`: Lists the Python dependencies.
- `.gitignore`: Specifies intentionally untracked files to ignore.

## Setup

1. Clone the repository:

   ```bash
   git clone <repository_url>
   cd x_automations
   ```

2. Create a virtual environment and activate it:

   ```bash
   python -m venv venv
   venv\Scripts\activate  # On Windows
   source venv/bin/activate  # On macOS/Linux
   ```

3. Install the dependencies:

   ```bash
   pip install -r requirements.txt
   ```

## Usage

To run the Streamlit application:

```bash
streamlit run streamlit_app.py
```
