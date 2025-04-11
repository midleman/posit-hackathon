
from openai import OpenAI

def analyze_test_results(test_run_diff, current_run_details, openai_api_key):
    print("🧠 Analyzing data with OpenAI...")
    client = OpenAI(api_key=openai_api_key)
    
    prompt = f"""Analyze {test_run_diff} and provide a summary of the changes.
        Only show sections that have data, do not comment about empty sections.
        Do not format the output as a markdown code block.
        Do not insert bullet points or any other formatting unless directed to do so.

        🔍 Patterns (only show this section if there are 4+ New Failures)
        Summarize any similar or repetitive errors?. Do any particular features seem to have multiple failures?
        If there is more than one observation, separate them on a new line with a bullet point.

        🔴 New Failures ({len(test_run_diff["New Failures"])}):
        Include very short error context if available, but omit stack traces or redundant info, summarize it in 35 characters or less.
        Do not include author.
        Do not include comment about consecutive failures/attempts.
        Always keep it VERY brief and to one line.
        If test title is more than 50 characters, truncate at 50 and add append "...
        Example:
        [e2e-browser] Feature > Test name — Timeout waiting for 'Preview'
        [e2e-electron] Feature > Test name — Timeout waiting for visibility
        [e2e-window] Feature > Test name — Interrupted run

        🫠 Still Failing ({len(test_run_diff["Still Failing"])}):
        Include note "Yx since Z".
        Do not include error analysis or observations.
        If test title is more than 50 characters, truncate at 50 and add append "...
        Example:
        [e2e-win] Feature > Test name (2x since [shorthand commitSHA])
        [e2e-browser] Feature > Test name (3x since [shorthand commitSHA])

        ⭐️ New Tests ({len(test_run_diff["New Tests"])}):
        If test title is more than 50 characters, truncate at 50 and add append "...
        No extra commentary, but include author name.
        Example:
        [groupId] Feature > Test name (by {current_run_details.get("meta", {}).get("commit", {}).get("authorName")})
        [e2e-electron] Login > Should be able to login (added by Marie Idleman)

        ✅ Resolved ({len(test_run_diff["Resolved"])}):
        If test title is more than 90 characters, truncate at 90 characters. (Resolved section only)
        No extra commentary.
        Example:
        [e2e-electron] Feature > Test name
        """
    
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        tools=[],
        tool_choice="auto",
    )
    
    return response.choices[0].message.content.strip()
