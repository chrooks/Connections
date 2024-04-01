"""
Utility functions for the Connections game API.

This module provides utility functions for making API requests,
parsing and validating request data, and creating JSON responses.

Functions:
- call_gpt_api(prompt): Calls the GPT API to generate words and their connections.
- parse_and_validate_request(required_fields): Parses and validates the request JSON payload.
- create_response(data, error, status_code): Creates a JSON response with the provided data or error message.
"""
import requests
from flask import request, jsonify


def call_llm_api(prompt):
    """
    Calls the LLM API to generate words and their connections based on the given prompt.

    :param prompt: The prompt to send to the LLM API.
    :return: A string containing categories and items (words) related to those categories.
    """
    # Make an API request to the LLM API
    api_url = "https://your-llm-api-url.com/generate"
    headers = {"Content-Type": "application/json", "Authorization": "Bearer your-api-key"}
    data = {"prompt": prompt, "max_tokens": 100, "temperature": 0.7}

    try:
        response = requests.post(api_url, headers=headers, json=data)
        response.raise_for_status()
        result = response.json()
        return result["choices"][0]["text"].strip()
    except requests.exceptions.RequestException as e:
        print(f"Error occurred while calling the LLM API: {e}")
        return ""
    except (KeyError, IndexError):
        print("Unexpected response format from the LLM API.")
        return ""


def parse_and_validate_request(required_fields):
    """
    Parses the request JSON payload and validates the presence of required fields.

    :param required_fields: A list of strings representing required field names.
    :return: A tuple of (data, error). If successful, data contains the parsed JSON
             and error is None. On failure, data is None and error contains an error message.
    """
    try:
        data = request.get_json(force=True)
        if not data:
            raise ValueError("Request payload is empty")

        missing_fields = [field for field in required_fields if field not in data]
        if missing_fields:
            raise ValueError(f"Missing required fields: {', '.join(missing_fields)}")

        return data, None
    except Exception as e:
        return None, str(e)


def create_response(data=None, error=None, status_code=200):
    """
    Creates a JSON response with the provided data or error message.

    :param data: The data to include in the response, if any.
    :param error: The error message to include in the response, if any.
    :param status_code: The HTTP status code for the response (default: 200).
    :return: A JSON response with the provided data or error message.
    """
    response = {}
    if data is not None:
        response["data"] = data
    if error is not None:
        response["error"] = error
    return jsonify(response), status_code
