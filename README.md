# JOB_MONITOR
Getting University job positions updated daily through Miniflux API, and leveraging locally Ollama LLM services to filer and summary job description, then doing email notification. Provide streamlit, fastapi backend and scheduler.


# Need to do before running

1. Apply Gmail API key, save it under ui directory and run gmail_init.py firstly to generate token.json which can be used future to send email.
2. If testing on Windwos and use WSL, please make sure enable Ubuntu, which was in Preferences-->WSL-->Integrations, this was based on my Rancher Desktop.
3. Running python main.py setup firstly to setup the database.
4. Miniflux runs on localhost:8080.

# TODO LIST
1. Currently only use jina.ai, should compare it with jina ReaderLM and Firecrawl as agent, of course different methods have pros and cons.
2. Build docker image for the whole workflow, easy to deploy.
