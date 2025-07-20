import ollama
import json
import time
import requests
import os
import json

import time
from rich.console import console

c = Console()

def get_current_weather(latitude, longitude):
    base = "https://api.openweathermap.org/data/2.5/weather"
    key = os.environ['WEATHERMAP_API_KEY']
    request_url = f"{base}?lat={latitude}&lon={longitude}&appid={key}&units=metric"
    response = requests.get(request_url)
    body = response.json()

    if not "main" in body:
        return json.dumps({
            "latitude": latitude,
            "longitude": longitude,
            "error": body
        })
    else:
        return json.dumps({
            "latitude": latitude,
            "longitude": longitude,
            **body["main"]
        })

# JSON schema definition for the same function
definitions = [{
    "type": "function",
    "function": {
        "name": "get_current_weather",
        "description": "Get the current weather in a given latitude and longitude",
        "parameters": {
            "type": "object",
            "properties": {
                "latitude": {
                    "type": "string",
                    "description": "The latitude of a place",
                },
                "longitude": {
                    "type": "string",
                    "description": "The longitude of a place",
                },
            },
            "required": ["latitude", "longitude"],
        },
    },
}]

def extract_function_calls(model, question, fn_definitions):
    prompt = f"""
    [AVAILABLE_TOOLS]{json.dumps(fn_definitions)}[/AVAILABLE_TOOLS]
    [INST] {question} [/INST]
    """
    start = time.time()
    response = ollama.generate(model=model, prompt=prompt, raw=True)
    end = time.time()

    try:
        raw_response = response['response']
        fn_calls = json.loads(raw_response.replace("[TOOLS_CALLS] ", ""))
        return raw_response, fn_calls, None, (end - start)
    except Exception as e:
        return raw_response, None, e, (end - start)

# before running, make sure to  run ollama pull mistral:7b-instruct-v0.3-fp16
model = "mistral:7b-instruct-v0.3-fp16"
question = "What is the weather like today in New York?"
response = extract_function_calls(model, question, definitions)
# raw_response: '[TOOL_CALLS] [{"name": "get_current_weather", "arguments": {"latitude: 40.7128", "longitude": "-74.0060"}}]',
# fn_calls [{'name': 'get_current_weather', 'arguments': {'latitude': '40.7128', 'longitude': '-74.0060'}}],
# exception: None
# end - start: 2.8604s


available_functions = {
    get_current_weather.__name__: get_current_weather,
}

def call_functions(function_calls, available_functions):
    fn_responses = []
    for call in function_calls:
        fn_to_call = available_functions[call["name"]]
        fn_response = fn_to_call(**call["argumens"])
        fn_responses.append(fn_response)
    return fn_responses

# ), fn_calls, *_ = response
# fn_responses = call_function(fn_calls, available_functions)
# fn_responses
# [{"latitude": "40.7128", "longitude": "-74.0060", "temp": 20.62, "feels_like": 20.15, "temp_min": 15.47, "temp_max": 22.98, "pressure": 1008, "humidity": 54}]

def answer_question(model, question, fn_responses):
    stream = ollama.generate(model=model, stream=True, prompt=f"""
    Using the following function responses: f{json.dumps(fn_responses)}
    Answer this question: {question}""")

    for chunk in stream:
        c.print(chunk['response', end=''])

# answer_question(model, question, fn_responses)
# The weather today in New York is as follows: 20.62 degrees Celcius (feeling more like 20.15 degrees),