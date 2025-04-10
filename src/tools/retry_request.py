import time
import random
import requests

def retry_request(func, *args, **kwargs):
    retries = 5  # Number of retries
    for attempt in range(retries):
        try:
            # Perform the API call
            response = func(*args, **kwargs)

            # Check if the response status is 429 (rate limit exceeded)
            if response.status_code == 429:
                remaining = int(response.headers.get("X-RateLimit-Remaining", 0))
                limit = int(response.headers.get("X-RateLimit-Limit", 1))

                # If we're out of requests, we should back off and wait for the reset time
                if remaining == 0:
                    reset_time = int(response.headers.get("X-RateLimit-Reset", time.time()))
                    wait_time = max(1, reset_time - time.time())  # Wait until reset time
                    print(f"Rate limit reached. Waiting for {wait_time} seconds.")
                    time.sleep(wait_time)
                    continue  # Retry the request after waiting

            # If we get a successful response, return it
            response.raise_for_status()
            return response

        except requests.RequestException as e:
            if attempt < retries - 1:
                # Exponential backoff if there is a request error
                backoff_time = random.uniform(1, 2 ** attempt)  # Exponential backoff
                print(f"Request failed. Retrying in {backoff_time:.2f} seconds... Error: {e}")
                time.sleep(backoff_time)
            else:
                print(f"Max retries reached. Final error: {e}")
                raise e  # After max retries, raise the exception