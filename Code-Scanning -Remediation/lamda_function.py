import json
import logging
import base64
import os
import boto3
import re
import requests
from urllib.parse import urlparse
from datetime import datetime
from botocore.exceptions import ClientError

# Set up logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize a Boto3 client for Bedrock
bedrock = boto3.client(service_name='bedrock-runtime')

# Fetch the GitHub token from environment variables
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')
if not GITHUB_TOKEN:
    raise ValueError("GitHub token is not set in the environment variables")

headers = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Content-Type": "application/json"
}

# Modified function to exclude specified folders
def fetch_repository_contents(repo_link, branch, path="", exclude_folders=None):
    repo_path = urlparse(repo_link).path.strip('/')
    api_endpoint = f"https://api.github.com/repos/{repo_path}/contents/{path}?ref={branch}"
    response = requests.get(api_endpoint, headers=headers)
    response.raise_for_status()
    
    files = {}
    for item in response.json():
        # Skip folders if they are in the exclude_folders list
        if item["type"] == "dir":
            folder_name = item["path"].split("/")[-1]
            if exclude_folders and folder_name in exclude_folders:
                logger.info(f"Skipping excluded folder: {folder_name}")
                continue
            # Recursively fetch contents from the subdirectory
            files.update(fetch_repository_contents(repo_link, branch, item["path"], exclude_folders))
        elif item["type"] == "file":
            file_content = requests.get(item["download_url"], headers=headers).text
            files[item["path"]] = file_content
    
    return files

def analyze_and_remediate_code(code_repo, non_code_exts):
    def analyze_code(code):
        prompt = f"\n\nHuman: Please analyze the following code:\n\nCode:\n{code}\n\nAssistant:"
        response = bedrock.invoke_model(
            body=json.dumps({
                "prompt": prompt,
                "max_tokens_to_sample": 1000,
                "temperature": 0.5,
                "top_k": 50,
                "top_p": 0.95,
                "stop_sequences": ["\n\nHuman:"]
            }),
            modelId="anthropic.claude-v2:1",
            contentType="application/json",
            accept="*/*"
        )
        analysis = json.loads(response['body'].read()).get('completion', '').strip()
        return re.findall(r"(potential security vulnerability|code style issue|performance issue|code complexity issue|potential bug)", analysis)

    def remediate_code(code, issues):
        # Updated prompt to ask for only code without any extra comments, delimiters, or explanations
        prompt = f"""
Human: Please fix the identified issues in the code below and return only the modified code without any explanations, summaries, or code block delimiters.

Code:
{code}

Issues identified:
{', '.join(issues)}

Assistant:"""
        
        response = bedrock.invoke_model(
            body=json.dumps({
                "prompt": prompt,
                "max_tokens_to_sample": 2000,
                "temperature": 0.7,
                "top_k": 50,
                "top_p": 0.95,
                "stop_sequences": ["\n\nHuman:"]
            }),
            modelId="anthropic.claude-v2:1",
            contentType="application/json",
            accept="*/*"
        )
        
        # Process the AI response to ensure only code is returned
        remediation = json.loads(response['body'].read()).get('completion', '').strip()

        # Strip out any unwanted parts like "Here is the fixed code" or code block delimiters
        remediation = re.sub(r"```[a-z]*", "", remediation).strip()  # Remove ```java or ``` if they exist
        remediation = remediation.replace("Here is the fixed code without any additional explanations or summaries:", "").strip()

        return remediation

    remediations = {}
    for file_path, file_content in code_repo.items():
        if any(file_path.endswith(ext) for ext in non_code_exts):
            logger.info(f"Skipping non-code file: {file_path}")
            continue
        issues = analyze_code(file_content)
        remediated_code = remediate_code(file_content, issues)
        remediations[file_path] = remediated_code
    return remediations

def create_new_branch(event):
    repo_link = event['repository_link']
    remediations = event['remediations']
    base_branch = event['base_branch']
    new_branch_name = event['new_branch_name']

    repo_path = urlparse(repo_link).path.strip('/')
    base_commit = requests.get(f"https://api.github.com/repos/{repo_path}/git/refs/heads/{base_branch}", headers=headers).json()["object"]["sha"]
    if requests.get(f"https://api.github.com/repos/{repo_path}/git/refs/heads/{new_branch_name}", headers=headers).status_code == 200:
        raise ValueError(f"Branch {new_branch_name} already exists.")
    requests.post(f"https://api.github.com/repos/{repo_path}/git/refs", json={"ref": f"refs/heads/{new_branch_name}", "sha": base_commit}, headers=headers)
    
    blobs = []
    for file_path, remediated_code in remediations.items():
        blob_payload = {
            "content": base64.b64encode(remediated_code.encode()).decode(),
            "encoding": "base64"
        }
        blob_sha = requests.post(f"https://api.github.com/repos/{repo_path}/git/blobs", json=blob_payload, headers=headers).json()["sha"]
        blobs.append({"path": file_path, "mode": "100644", "type": "blob", "sha": blob_sha})

    base_tree_sha = requests.get(f"https://api.github.com/repos/{repo_path}/git/trees/{base_commit}", headers=headers).json()["sha"]
    new_tree_sha = requests.post(f"https://api.github.com/repos/{repo_path}/git/trees", json={"base_tree": base_tree_sha, "tree": blobs}, headers=headers).json()["sha"]
    new_commit_sha = requests.post(f"https://api.github.com/repos/{repo_path}/git/commits", json={"message": "Remediated code", "tree": new_tree_sha, "parents": [base_commit]}, headers=headers).json()["sha"]
    requests.patch(f"https://api.github.com/repos/{repo_path}/git/refs/heads/{new_branch_name}", json={"sha": new_commit_sha}, headers=headers)
    
    return new_branch_name

def lambda_handler(event, context):
    try:
        agent = event['agent']
        actionGroup = event['actionGroup']
        function = event['function']
        parameters = event.get('parameters', {})
        print(parameters)
        properties = {param["name"]: param["value"] for param in parameters}
        repo_link = properties.get('repository_url')
        branch = properties.get('branch_name')
        non_code_exts = properties.get('file_extensions_to_exclude')
        exclude_folders = properties.get('folders_to_exclude')
        new_branch_name = properties.get('new_remediated_branch_name')

        # Fetch repository contents, excluding specified folders
        code_repo = fetch_repository_contents(repo_link, branch, exclude_folders=exclude_folders)
        remediations = analyze_and_remediate_code(code_repo, non_code_exts)

        create_branch_event = {
            'repository_link': repo_link,
            'remediations': remediations,
            'base_branch': branch,
            'new_branch_name': new_branch_name
        }
        
        new_branch_name = create_new_branch(create_branch_event)
        
        responseBody = {
            "TEXT": {
                "body": new_branch_name
            }
        }

        # Prepare the action response
        action_response = {
            'actionGroup': actionGroup,
            'function': function,
            'functionResponse': {
                'responseBody': responseBody
            }
        }

        # Final response structure expected by Bedrock agent
        final_response = {'response': action_response, 'messageVersion': event['messageVersion']}
        logger.info("Response: %s", json.dumps(final_response))

        return final_response

    except KeyError as ke:
        logger.error(f"Key error: {str(ke)}")
        responseBody = {
            "TEXT": {
                "body": f"Missing required information: {str(ke)}"
            }
        }
        action_response = {
            'actionGroup': actionGroup,
            'function': function,
            'functionResponse': {
                'responseBody': responseBody
            }
        }
        final_response = {'response': action_response, 'messageVersion': event['messageVersion']}
        return final_response

    except Exception as e:
        logger.error("An error occurred: %s", e, exc_info=True)
        responseBody = {
            "TEXT": {
                "body": f"Error: {str(e)}"
            }
        }
        action_response = {
            'actionGroup': actionGroup,
            'function': function,
            'functionResponse': {
                'responseBody': responseBody
            }
        }
        final_response = {'response': action_response, 'messageVersion': event['messageVersion']}
        return final_response

