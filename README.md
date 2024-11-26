### Code Scanning and Remediation using Amazon Bedrock and GitHub

---

#### Overview
This README documents an AWS Lambda function designed to scan and remediate code repositories using Amazon Bedrock and GitHub. The solution automates the process of identifying and fixing code issues by leveraging Bedrock's large language model (LLM) and GitHub's API. The solution follows best practices for secure and efficient code management.

#### Solution Overview
- The user specifies the repository link and branch name to be scanned and remediated.
- The Lambda function fetches the repository contents and uses Bedrock's LLM to analyze the code for potential issues.
- Based on the identified issues, the function generates remediation suggestions and updates the code.
- The updated code is committed to a new branch in the same repository, and the user is notified of the changes.

#### Solution Workflow:
The below diagram pictorially represents how the solution works.
 ![Workflow](Assets/code-scanner-arch-diagram-latest.png) 
 

#### Code Scanning and Remediation Lambda
- **Description**: Automates code scanning and remediation by leveraging Amazon Bedrock's LLM and GitHub API.
- **Environment Variables**:
  - `GITHUB_TOKEN`: Token for GitHub API authentication.
- **Dependencies**: Python 3.x, requests, boto3, logging, base64, re libraries.
- **Logical Flow**:
  1. Receives an event with repository details.
  2. Fetches repository contents from GitHub.
  3. Analyzes code using Bedrock LLM to identify issues.
  4. Generates remediation suggestions and updates the code.
  5. Commits the updated code to a new branch in the repository.
  6. Returns success or error message.


#### Setting up the Lambda Function

- **Create the Lambda Function**:

  1. Create a new Lambda function in the AWS Management Console.
  2. Set up the function with the provided code.
  3. Configure environment variables, particularly GITHUB_TOKEN.
  4. Install required dependencies (requests, boto3, re).

- **Configure GitHub Repository**:

  1. Generate a GitHub token with appropriate permissions.
  2. Add the token to the Lambda function's environment variables.

- **Invoke the Lambda Function**:

  1. The function can be invoked manually or integrated with other AWS services like API Gateway for automated triggers.

#### Sample JSON for Lambda Invocation

```
{
    "repository_link": "https://github.com/your-username/your-repository",
    "repository_name": "your-repository",
    "branch_name": "your-branch-to-scan",
    "non_code_extensions": [".md", ".txt", ".gitignore"],
    "folders_to_exclude": ["docs", "test"]
    "new_branch_name": "your-new-remediation-branch"
}

```

#### Receives an event with repository details

```
repo_link = properties['repository_link']
branch = properties['branch_name']
non_code_exts = properties['non_code_extensions']
folders_exclude = properties['folders_to_exclude']
new_branch_name = properties['new_branch_name']

```


#### Updating and Maintenance
- **Lambda Functions**:
  - Regularly update dependencies and environment variables.
  - Monitor Lambda logs for troubleshooting.


## Security

See [CONTRIBUTING](CONTRIBUTING.md#security-issue-notifications) for more information.

## License

This library is licensed under the MIT-0 License. See the LICENSE file.

