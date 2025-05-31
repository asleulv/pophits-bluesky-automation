# Pop Hits Bluesky Automation

This project automates posting random songs from PopHits.org to Bluesky.

## Installation

1.  Clone the repository:
    ```bash
    git clone <repository_url>
    cd <repository_directory>
    ```

2.  Create a virtual environment:
    ```bash
    python3 -m venv venv
    ```

3.  Activate the virtual environment:
    ```bash
    source venv/bin/activate  # On Unix
    venv\Scripts\activate  # On Windows
    ```

4.  Install the requirements:
    ```bash
    pip install -r requirements.txt
    ```

## Running the script

1.  Set the required environment variables. Create a `.env` file with the following variables:

    ```
    POPHITS_BLUESKY_USERNAME=<your_bluesky_username>
    POPHITS_BLUESKY_PASSWORD=<your_bluesky_password>
    ```

2.  Run the script:
    ```bash
    python bluesky_song_poster.py
    ```

## Scheduling with Cron (Unix)

To schedule the script to run automatically on a Unix system, you can use cron.

1.  Open the crontab editor:
    ```bash
    crontab -e
    ```

2.  Add the following line to the crontab file to run the script daily:

    ```cron
    0 1 * * * /usr/bin/python3 /path/to/bluesky_song_poster.py
    ```

    *   The line runs `bluesky_song_poster.py` at 1 AM (01:00).
    *   Make sure to replace `/path/to/` with the actual path to the script.
    *   You may need to activate the virtual environment within the cron job by sourcing the activate script. You can do this by creating a shell script that activates the environment and then runs the Python script, and then calling that shell script from cron.
    ```bash
    #!/bin/bash
    source venv/bin/activate
    python /path/to/bluesky_song_poster.py
    ```
=======
This project automates posting Billboard chart information and random songs from PopHits.org to Bluesky.