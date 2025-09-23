from config.config_loader import config_loader

class PromptTemplates:
    @staticmethod
    def get_job_analysis_prompt(job_title: str, job_source: str, job_published: str, job_link: str, job_category: str, job_description: str, job_content: str, keywords: list) -> str:
        """Generate prompt for job posting analysis"""
        keywords_str = ", ".join(keywords)
        
        # 招聘条件：身份是国际学生，还是美国公民，基于博士学历
        # 大学限制：R1 optional
        prompt = f"""
Please analyze the following job posting and extract structured information in markdown format.

Job Title: {job_title}

Job Content:
{job_content}
{job_description}

Keywords to look for: {keywords_str}

Please provide the analysis in the following markdown format:

## Title
{job_title}

## Source
{job_source}

## Posted Date
{job_published}

## Deadline
[Extract application deadline if available]

## Application Link
{job_link}

## Location
[Extract location if available]

## Salary
[Extract salary range if available]

## Keywords
[List relevant keywords from the provided list that match this job]

## Recruitment requirements
[Extract specific requirements such as citizenship status, degree requirements, experience, etc.]

## Summary
[Provide a details summary in Chinese (中文), highlighting key requirements, responsibilities, qualifications and other important information. Use bullet points if necessary.]

Instructions:
1. Keep English information in English as specified
2. Provide Chinese summary only for the Summary section
3. If information is not available, write "Not specified"
4. Only include keywords that are actually relevant to this job posting
5. IMPORTANT: The content format varies by source. Look for key information anywhere in the text:
   - Job titles, department names, salary ranges, locations, how to apply, skills, etc.
   - Application deadlines (dates, "until filled", etc.)
   - Requirements and qualifications sections
   - Contact information or application URLs
   - Extract information regardless of its position in the content
6. Carefully check for phrases like "US citizens only", "no visa sponsorship", "permanent residents", "international students welcome"
"""
        return prompt
    
    @staticmethod
    def get_search_query_prompt(user_query: str) -> str:
        """Generate prompt for semantic search queries"""
        return f"""
Convert the following user query into relevant search terms for finding academic job postings:

User Query: {user_query}

Generate 3-5 relevant search terms or phrases that would help find matching job postings.
Focus on job titles, departments, qualifications, and key requirements.

Search Terms:
"""

prompt_templates = PromptTemplates()