import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from collector.db import db_manager
from analysis.vector_store import vector_store
from collector.scheduler import job_scheduler
from config.config_loader import config_loader

def main():
    st.set_page_config(page_title="Job Monitor", layout="wide")
    
    st.title("🎯 Academic Job Monitor")
    st.sidebar.title("Navigation")
    
    # Sidebar navigation
    page = st.sidebar.selectbox(
        "Choose a page",
        ["Job Dashboard", "Search Jobs", "Configuration", "System Status"]
    )
    
    if page == "Job Dashboard":
        show_job_dashboard()
    elif page == "Search Jobs":
        show_search_page()
    elif page == "Configuration":
        show_configuration()
    elif page == "System Status":
        show_system_status()

def show_job_dashboard():
    st.header("Recent Job Postings")
    
    # Filter controls
    col1, col2 = st.columns([3, 1])
    
    with col1:
        search_term = st.text_input("Search in titles and descriptions:")
    
    with col2:
        limit = st.number_input("Number of jobs", min_value=10, max_value=100, value=20)
    
    # Get jobs
    if search_term:
        jobs = db_manager.search_entries(search_term, limit)
    else:
        jobs = db_manager.get_all_entries(limit)
    
    if not jobs:
        st.info("No jobs found. The system may be still collecting data.")
        return
    
    # Display jobs
    for job in jobs:
        with st.expander(f"📋 {job.title} - {job.source}"):
            col1, col2 = st.columns([3, 1])
            
            with col1:
                if job.analysis_result:
                    st.markdown(job.analysis_result)
                else:
                    st.write(job.description[:500] + "..." if len(job.description) > 500 else job.description)
            
            with col2:
                st.write(f"**Published:** {job.published}")
                st.write(f"**Source:** {job.source}")
                if job.link:
                    st.markdown(f"[🔗 View Job]({job.link})")

def show_search_page():
    st.header("🔍 Semantic Job Search")
    
    query = st.text_input("Enter your search query:", 
                         placeholder="e.g., tenure-track Curriculum & Instruction jobs")
    
    col1, col2 = st.columns([2, 1])
    with col1:
        time_filter = st.selectbox(
            "Time range:",
            ["All time", "Past 3 months", "Past 6 months", "Past 1 year"]
        )
    
    with col2:
        max_results = st.number_input("Max results:", min_value=5, max_value=50, value=10)
    
    if st.button("🚀 Search") and query:
        with st.spinner("Searching..."):
            time_filter_str = time_filter if time_filter != "All time" else None
            results = vector_store.semantic_search(query, time_filter_str)
            
            if results:
                st.success(f"Found {len(results)} relevant jobs")
                
                for i, result in enumerate(results[:max_results], 1):
                    with st.expander(f"{i}. {result['title']} (Score: {result['similarity_score']:.3f})"):
                        col1, col2 = st.columns([3, 1])
                        
                        with col1:
                            if result.get('analysis'):
                                st.markdown(result['analysis'])
                            else:
                                st.write(result['text'][:500] + "...")
                        
                        with col2:
                            st.write(f"**Source:** {result['source']}")
                            st.write(f"**Published:** {result['published']}")
                            if result.get('link'):
                                st.markdown(f"[🔗 View Job]({result['link']})")
            else:
                st.info("No matching jobs found. Try different search terms.")

def show_configuration():
    st.header("⚙️ System Configuration")
    
    # RSS Feeds Configuration
    st.subheader("RSS Feeds")
    config = config_loader.config
    
    feeds = config.get('rss_feeds', [])
    
    # Display current feeds
    for i, feed in enumerate(feeds):
        col1, col2, col3 = st.columns([2, 2, 1])
        with col1:
            feeds[i]['name'] = st.text_input(f"Feed {i+1} Name:", value=feed['name'], key=f"feed_name_{i}")
        with col2:
            feeds[i]['url'] = st.text_input(f"Feed {i+1} URL:", value=feed['url'], key=f"feed_url_{i}")
        with col3:
            if st.button(f"Remove", key=f"remove_feed_{i}"):
                feeds.pop(i)
                st.rerun()
    
    # Add new feed
    col1, col2, col3 = st.columns([2, 2, 1])
    with col1:
        new_feed_name = st.text_input("New Feed Name:")
    with col2:
        new_feed_url = st.text_input("New Feed URL:")
    with col3:
        if st.button("Add Feed") and new_feed_name and new_feed_url:
            feeds.append({
                'name': new_feed_name,
                'url': new_feed_url,
                'category': 'academic'
            })
            config_loader.update_feeds(feeds)
            st.success("Feed added!")
            st.rerun()
    
    if st.button("Save Feeds"):
        config_loader.update_feeds(feeds)
        st.success("Feeds configuration saved!")
    
    st.divider()
    
    # Keywords Configuration
    st.subheader("Search Keywords")
    keywords = config.get('keywords', [])
    
    # Display current keywords
    keywords_text = st.text_area(
        "Keywords (one per line):",
        value='\n'.join(keywords),
        height=150
    )
    
    if st.button("Save Keywords"):
        new_keywords = [k.strip() for k in keywords_text.split('\n') if k.strip()]
        config_loader.update_keywords(new_keywords)
        st.success("Keywords saved!")
    
    st.divider()
    
    # Scheduler Configuration
    st.subheader("Scheduler Settings")
    col1, col2 = st.columns(2)
    
    with col1:
        current_interval = config['scheduler']['fetch_interval_hours']
        new_interval = st.number_input("Fetch Interval (hours):", min_value=1, max_value=24, value=current_interval)
    
    with col2:
        current_digest_time = config['scheduler']['digest_time']
        new_digest_time = st.text_input("Daily Digest Time (HH:MM):", value=current_digest_time)
    
    if st.button("Save Scheduler Settings"):
        config = config_loader.config
        config['scheduler']['fetch_interval_hours'] = new_interval
        config['scheduler']['digest_time'] = new_digest_time
        config_loader.save_yaml_config(config)
        st.success("Scheduler settings saved! Restart required.")
    
    st.divider()

    # RSS Mode Configuration
    st.subheader("RSS Collection Mode")
    current_mode = config.get('rss_mode', 'auto')
    new_mode = st.selectbox(
        "RSS Collection Mode:",
        options=['auto', 'direct', 'miniflux', 'freshrss'],
        index=['auto', 'direct', 'miniflux', 'freshrss'].index(current_mode),
        help="auto: detect from .env, direct: use feedparser, miniflux/freshrss: use API"
    )

    if st.button("Save RSS Mode"):
        config = config_loader.config
        config['rss_mode'] = new_mode
        config_loader.save_yaml_config(config)
        st.success("RSS mode saved! Restart required.")

def show_system_status():
    st.header("📊 System Status")
    
    # Job Statistics
    total_jobs = len(db_manager.get_all_entries(limit=10000))
    unanalyzed_jobs = len(db_manager.get_unanalyzed_entries())
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Jobs", total_jobs)
    with col2:
        st.metric("Analyzed Jobs", total_jobs - unanalyzed_jobs)
    with col3:
        st.metric("Pending Analysis", unanalyzed_jobs)
    
    # Recent Activity
    st.subheader("Recent Jobs")
    recent_jobs = db_manager.get_all_entries(limit=10)
    
    if recent_jobs:
        df_data = []
        for job in recent_jobs:
            df_data.append({
                'Title': job.title[:50] + "..." if len(job.title) > 50 else job.title,
                'Source': job.source,
                'Published': job.published,
                'Analyzed': "✅" if job.analyzed else "⏳"
            })
        
        df = pd.DataFrame(df_data)
        st.dataframe(df, use_container_width=True)
    
    # System Actions
    st.subheader("System Actions")
    
    col1, col2, col3, col4= st.columns(4)
    
    with col1:
        if st.button("🔄 Force Fetch Now"):
            with st.spinner("Fetching jobs..."):
                job_scheduler.fetch_and_analyze_jobs()
                st.success("Jobs fetched and queued for analysis!")
    
    with col2:
        if st.button("🧠 Analyze Pending"):
            with st.spinner("Analyzing jobs..."):
                job_scheduler.analyze_pending_jobs()
                st.success("Pending jobs analyzed!")
    
    with col3:
        if st.button("🔄 Rebuild Index"):
            with st.spinner("Rebuilding vector index..."):
                vector_store.rebuild_index()
                st.success("Vector index rebuilt!")
    
    # Add this in the System Actions section, after existing buttons
    with col4:  # Add a 4th column
        hours_back = st.number_input("Hours back:", min_value=1, max_value=168, value=24, key="digest_hours")
        if st.button("📧 Send Digest"):
            with st.spinner("Sending digest..."):
                from ui.email_digest import email_digest
                success = email_digest.send_manual_digest(hours_back)
                if success:
                    st.success(f"Digest sent for last {hours_back} hours!")
                else:
                    st.error("Failed to send digest or no jobs found")

if __name__ == "__main__":
    # Start scheduler on app startup
    if 'scheduler_started' not in st.session_state:
        job_scheduler.start()
        st.session_state.scheduler_started = True
    
    main()