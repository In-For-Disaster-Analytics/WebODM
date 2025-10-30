"""
JWT Node Wrapper for ClusterODM integration

This module provides a wrapper around the pyodm Node class to add JWT token support
for ClusterODM integration with Tapis authentication.
"""

import logging
import os
from urllib.parse import urlencode

import requests
from pyodm import Node
from pyodm.exceptions import NodeServerError, NodeConnectionError
from pyodm.types import TaskStatus

logger = logging.getLogger('app.logger')


class JWTTokenExpiredError(Exception):
    """Custom exception for JWT token expiration that can be handled by the frontend."""
    pass


class JWTNodeWrapper:
    """
    A wrapper around pyodm Node that adds JWT token support for ClusterODM.
    
    ClusterODM expects JWT tokens to be passed as a 'token' query parameter
    in API requests, which pyodm doesn't support natively.
    """
    
    def __init__(self, hostname, port, token, timeout, jwt_token):
        """
        Initialize the JWT-enabled node wrapper.
        
        :param hostname: Processing node hostname
        :param port: Processing node port  
        :param token: Processing node token (if any)
        :param timeout: Request timeout
        :param jwt_token: JWT token for Tapis authentication
        """
        self.hostname = hostname
        self.port = port
        self.token = token
        self.timeout = timeout
        self.jwt_token = jwt_token
        self.auth_token = jwt_token if jwt_token else token
        # Use HTTPS for port 443, HTTP for others
        protocol = "https" if port == 443 else "http"
        self.base_url = f"{protocol}://{hostname}:{port}"
        
        # Create underlying Node instance for fallback operations
        self._node = Node(hostname, port, token, timeout)
        
        if self.jwt_token:
            logger.info(f"Created JWTNodeWrapper for {hostname}:{port} with JWT token")
        elif self.token:
            logger.info(f"Created JWTNodeWrapper for {hostname}:{port} using node token")
        else:
            logger.info(f"Created JWTNodeWrapper for {hostname}:{port} without authentication token")
    
    def _apply_auth_token(self, params):
        if self.auth_token:
            params['token'] = self.auth_token
    
    def create_task(self, images, options, name=None, progress_callback=None):
        """
        Create a new task on the processing node with JWT token support.
        
        This method replicates pyodm's create_task functionality but adds
        JWT token support by including it as a query parameter.
        """
        try:
            # Check if we have images to process
            if not images or len(images) == 0:
                error_msg = "No files uploaded."
                logger.error(error_msg)
                raise Exception(error_msg)
            
            # Build the URL with JWT token as query parameter
            endpoint = f"{self.base_url}/task/new"
            params = {}
            self._apply_auth_token(params)
                
            if params:
                endpoint += "?" + urlencode(params)
            
            token_label = "JWT token" if self.jwt_token else ("node token" if self.token else "no token")
            logger.info(f"Creating task via ClusterODM at: {endpoint} (auth={token_label})")
            logger.info(f"Number of images provided: {len(images)}")
            if len(images) > 0:
                logger.info(f"First image path: {images[0]}")
            
            # Prepare the form data
            files = []
            for image_path in images:
                logger.info(f"Processing image path: {image_path}")
                try:
                    if not os.path.exists(image_path):
                        logger.error(f"Image file does not exist: {image_path}")
                        raise FileNotFoundError(f"Image file does not exist: {image_path}")
                    files.append(('images', open(image_path, 'rb')))
                except Exception as e:
                    logger.error(f"Failed to open image file {image_path}: {str(e)}")
                    raise
            
            data = {}
            if name:
                data['name'] = name
            
            # Convert options to the format expected by NodeODM/ClusterODM
            if options:
                import json
                data['options'] = json.dumps([{'name': k, 'value': v} for k, v in options.items()])
            else:
                data['options'] = '[]'
            
            # Log detailed request information
            logger.info(f"=== HTTP REQUEST DETAILS ===")
            logger.info(f"Method: POST")
            logger.info(f"URL: {endpoint}")
            logger.info(f"Query Parameters: {params}")
            logger.info(f"Form Data: {data}")
            logger.info(f"Files: {[f[0] for f in files]} ({len(files)} files)")
            logger.info(f"Timeout: {self.timeout}s")
            logger.info(f"==============================")
            
            # Make the request
            try:
                response = requests.post(endpoint, files=files, data=data, timeout=self.timeout)
            except requests.exceptions.ConnectionError as e:
                logger.error(f"Connection error when creating task: {str(e)}")
                raise Exception(f"Failed to connect to ClusterODM: {str(e)}")
            except requests.exceptions.Timeout as e:
                logger.error(f"Timeout error when creating task: {str(e)}")
                raise Exception(f"Request to ClusterODM timed out: {str(e)}")
            except requests.exceptions.RequestException as e:
                logger.error(f"Request error when creating task: {str(e)}")
                raise Exception(f"Request failed: {str(e)}")
            
            # Log detailed response information
            logger.info(f"=== HTTP RESPONSE DETAILS ===")
            logger.info(f"Status Code: {response.status_code}")
            logger.info(f"Response Headers: {dict(response.headers)}")
            logger.info(f"Response Content Length: {len(response.content)} bytes")
            if response.headers.get('content-type', '').startswith('application/json'):
                try:
                    response_json = response.json()
                    logger.info(f"Response JSON: {response_json}")
                except:
                    logger.info(f"Response Text: {response.text[:1000]}...")
            else:
                logger.info(f"Response Text: {response.text[:1000]}...")
            logger.info(f"===============================")
            
            # Close file handles
            for _, file_handle in files:
                file_handle.close()

            # Check for authentication errors first
            if response.status_code == 401:
                try:
                    error_data = response.json()
                    if 'error' in error_data and 'Authentication expired' in error_data.get('message', ''):
                        # This is a token expiration error - trigger frontend handling
                        logger.error(f"JWT token expired for ClusterODM task creation")
                        raise JWTTokenExpiredError("Your Tapis session has expired. Please refresh the page to re-authenticate.")
                except ValueError:
                    # Not JSON response, treat as generic auth error
                    pass

                error_msg = f"Authentication failed: HTTP 401 - {response.text}"
                logger.error(error_msg)
                raise Exception(error_msg)

            if response.status_code == 200:
                try:
                    result = response.json()
                except ValueError as e:
                    logger.error(f"Invalid JSON response: {response.text}")
                    raise Exception(f"Invalid JSON response from ClusterODM: {str(e)}")

                if 'uuid' in result:
                    # Create a task-like object that has the uuid attribute
                    class TaskResult:
                        def __init__(self, uuid):
                            self.uuid = uuid

                    logger.info(f"Successfully created task with UUID: {result['uuid']}")
                    return TaskResult(result['uuid'])
                elif 'error' in result:
                    error_msg = f"ClusterODM returned error: {result['error']}"
                    logger.error(error_msg)
                    raise Exception(error_msg)
                else:
                    error_msg = f"No UUID in response: {result}"
                    logger.error(error_msg)
                    raise Exception(error_msg)
            else:
                error_msg = f"Failed to create task: HTTP {response.status_code} - {response.text}"
                logger.error(error_msg)
                raise Exception(error_msg)
                
        except Exception as e:
            logger.error(f"Error creating task with JWT token: {str(e)}")
            raise
    
    def _fetch_task_info(self, uuid, with_output=None):
        params = {}
        self._apply_auth_token(params)

        if with_output is not None:
            if isinstance(with_output, bool):
                if with_output:
                    params['with_output'] = 0
            else:
                try:
                    params['with_output'] = max(0, int(with_output))
                except (TypeError, ValueError):
                    logger.warning(f"[JWTNodeWrapper] Invalid with_output value '{with_output}', ignoring")

        endpoint = f"{self.base_url}/task/{uuid}/info"
        if params:
            endpoint += "?" + urlencode(params)

        logger.info(f"=== HTTP REQUEST DETAILS (Task Info) ===")
        logger.info(f"Method: GET")
        logger.info(f"URL: {endpoint}")
        logger.info(f"Query Parameters: {params}")
        logger.info(f"Auth: {'jwt' if self.jwt_token else ('node' if self.token else 'none')}")
        logger.info(f"Timeout: {self.timeout}s")
        logger.info(f"=========================================")

        response = requests.get(endpoint, timeout=self.timeout)

        logger.info(f"=== HTTP RESPONSE DETAILS (Task Info) ===")
        logger.info(f"Status Code: {response.status_code}")
        logger.info(f"Response Headers: {dict(response.headers)}")
        logger.info(f"Response Content Length: {len(response.content)} bytes")
        if response.headers.get('content-type', '').startswith('application/json'):
            try:
                response_json = response.json()
                logger.info(f"Response JSON: {response_json}")
            except Exception:
                logger.info(f"Response Text: {response.text[:1000]}...")
        else:
            logger.info(f"Response Text: {response.text[:1000]}...")
        logger.info(f"==========================================")

        if response.status_code != 200:
            error_msg = f"Failed to get task info: HTTP {response.status_code} - {response.text}"
            logger.error(error_msg)
            if response.status_code in (502, 503, 504):
                raise NodeConnectionError(error_msg)
            raise Exception(error_msg)

        data = response.json()

        if 'error' in data:
            logger.error(f"ClusterODM returned error: {data['error']}")
            raise NodeServerError(f"ClusterODM error: {data['error']}")

        if 'uuid' not in data:
            logger.error("ClusterODM response missing required 'uuid' field")
            raise NodeServerError("ClusterODM response missing required 'uuid' field")

        if 'options' not in data:
            logger.warning("ClusterODM response missing 'options' field, adding empty options")
            data['options'] = []

        if 'output' not in data or data['output'] is None:
            data['output'] = []
        elif isinstance(data['output'], str):
            data['output'] = data['output'].splitlines()

        return data

    def _fetch_task_output(self, uuid, line=0):
        params = {'line': max(0, int(line))}
        self._apply_auth_token(params)

        endpoint = f"{self.base_url}/task/{uuid}/output"
        if params:
            endpoint += "?" + urlencode(params)

        logger.info(f"=== HTTP REQUEST DETAILS (Task Output) ===")
        logger.info(f"Method: GET")
        logger.info(f"URL: {endpoint}")
        logger.info(f"Query Parameters: {params}")
        logger.info(f"Auth: {'jwt' if self.jwt_token else ('node' if self.token else 'none')}")
        logger.info(f"Timeout: {self.timeout}s")
        logger.info(f"==========================================")

        response = requests.get(endpoint, timeout=self.timeout)

        logger.info(f"=== HTTP RESPONSE DETAILS (Task Output) ===")
        logger.info(f"Status Code: {response.status_code}")
        logger.info(f"Response Headers: {dict(response.headers)}")
        logger.info(f"Response Content Length: {len(response.content)} bytes")

        if response.status_code == 200:
            text = response.text
            logger.info(f"Output Text Preview: {text[:500]}...")
            logger.info(f"============================================")
            return text

        error_text = response.text
        logger.warning(f"Failed to get task output. Status: {response.status_code}")
        logger.warning(f"Error Response: {error_text}")
        logger.info(f"============================================")

        if ("no task table entry" in error_text.lower() or
                "invalid route" in error_text.lower() or
                response.status_code == 404):
            return f"Task not found on ClusterODM (UUID: {uuid})\n\nThis task may have been processed on a different node or removed.\nNo console output is available."
        if response.status_code in (401, 403):
            return f"Authentication failed when retrieving output for task {uuid}\n\nThis may indicate a JWT token issue.\nError: {error_text}"
        return f"Unable to retrieve output for task {uuid}\n\nHTTP Status: {response.status_code}\nError: {error_text}\n\nThis task may be in an error state or not accessible."

    def _download_task_zip(self, uuid, destination, progress_callback=None, parallel_downloads=1):
        tokens_to_try = []
        if self.auth_token:
            tokens_to_try.append(self.auth_token)
        if self.token and self.token not in tokens_to_try:
            tokens_to_try.append(self.token)
        tokens_to_try.append(None)

        last_error = None

        for idx, token in enumerate(tokens_to_try):
            params = {}
            if token:
                params['token'] = token

            zip_endpoint = f"{self.base_url}/task/{uuid}/download/all.zip"
            if params:
                zip_endpoint += "?" + urlencode(params)

            if token:
                if token == self.auth_token and token == self.jwt_token:
                    token_label = "jwt"
                elif token == self.token:
                    token_label = "node"
                else:
                    token_label = "custom"
            else:
                token_label = "none"
            attempt_info = f"[attempt {idx + 1}/{len(tokens_to_try)} | token={token_label}]"
            logger.info(f"[JWTNodeWrapper] Downloading task assets from {zip_endpoint} {attempt_info}")

            try:
                with requests.get(zip_endpoint, stream=True, timeout=self.timeout) as response:
                    if response.status_code != 200:
                        error_text = response.text[:500]
                        logger.warning(f"[JWTNodeWrapper] Download attempt failed for {uuid} {attempt_info}: "
                                       f"{response.status_code} - {error_text}")
                        if idx + 1 < len(tokens_to_try):
                            last_error = (response.status_code, error_text)
                            continue
                        raise NodeServerError(
                            f"ClusterODM download failed with status {response.status_code}: {error_text}"
                        )

                    total_size = int(response.headers.get('content-length', 0))
                    downloaded = 0
                    chunk_size = 1024 * 1024

                    os.makedirs(destination, exist_ok=True)
                    temp_path = os.path.join(destination, f"{uuid}_all.zip.download")
                    final_path = os.path.join(destination, f"{uuid}_all.zip")

                    with open(temp_path, 'wb') as file_handle:
                        for chunk in response.iter_content(chunk_size=chunk_size):
                            if not chunk:
                                continue
                            file_handle.write(chunk)
                            downloaded += len(chunk)

                            if progress_callback:
                                try:
                                    progress = (downloaded / total_size) * 100.0 if total_size > 0 else 0.0
                                    progress_callback(progress)
                                except Exception as progress_error:
                                    logger.debug(f"[JWTNodeWrapper] Progress callback raised: {progress_error}")

                    os.replace(temp_path, final_path)
                    logger.info(f"[JWTNodeWrapper] Assets downloaded for task {uuid} -> {final_path}")
                    return final_path
            except requests.exceptions.RequestException as e:
                logger.warning(f"[JWTNodeWrapper] Request error downloading assets {attempt_info}: {str(e)}")
                last_error = (None, str(e))
                if idx + 1 < len(tokens_to_try):
                    continue
                raise NodeServerError(f"Error downloading assets from ClusterODM: {str(e)}")
            except NodeServerError:
                raise
            except Exception as e:
                logger.warning(f"[JWTNodeWrapper] Unexpected error downloading assets {attempt_info}: {str(e)}")
                last_error = (None, str(e))
                if idx + 1 < len(tokens_to_try):
                    continue
                raise

        if last_error:
            status, message = last_error
            if status is not None:
                raise NodeServerError(f"ClusterODM download failed with status {status}: {message}")
            raise NodeServerError(f"ClusterODM download failed: {message}")
    
    def get_task(self, uuid):
        """
        Get task with JWT token support for task info queries.
        """
        try:
            task_info_data = self._fetch_task_info(uuid)

            class TaskWrapper:
                def __init__(self, uuid, task_info_data, wrapper, auth_token, timeout):
                    self.uuid = uuid
                    self._info_data = task_info_data
                    self._wrapper = wrapper
                    self.base_url = wrapper.base_url
                    self.auth_token = auth_token
                    self.timeout = timeout

                def info(self, with_output=True):
                    if self._wrapper:
                        try:
                            fetched = self._wrapper._fetch_task_info(self.uuid, with_output)
                            self._info_data = fetched
                        except Exception as e:
                            logger.warning(f"[JWTNodeWrapper] Failed to fetch task info with output: {str(e)}")
                    if 'output' not in self._info_data or self._info_data['output'] is None:
                        self._info_data['output'] = []
                    elif isinstance(self._info_data['output'], str):
                        self._info_data['output'] = self._info_data['output'].splitlines()
                    from pyodm.types import TaskInfo
                    return TaskInfo(self._info_data)

                def output(self, line=0):
                        # For console output, we need to make another request
                        output_endpoint = f"{self.base_url}/task/{self.uuid}/output"
                        params = {'line': line}
                        if self.auth_token:
                            params['token'] = self.auth_token

                        if params:
                            output_endpoint += "?" + urlencode(params)

                        logger.info(f"=== HTTP REQUEST DETAILS (Task Output) ===")
                        logger.info(f"Method: GET")
                        logger.info(f"URL: {output_endpoint}")
                        logger.info(f"Query Parameters: {params}")
                        logger.info(f"==========================================")

                        try:
                            output_response = requests.get(output_endpoint, timeout=self.timeout)

                            logger.info(f"=== HTTP RESPONSE DETAILS (Task Output) ===")
                            logger.info(f"Status Code: {output_response.status_code}")
                            logger.info(f"Response Headers: {dict(output_response.headers)}")
                            logger.info(f"Response Content Length: {len(output_response.content)} bytes")

                            if output_response.status_code == 200:
                                output_text = output_response.text
                                logger.info(f"Output Text Preview: {output_text[:500]}...")
                                logger.info(f"============================================")
                                return output_text
                            else:
                                error_text = output_response.text
                                logger.warning(f"Failed to get task output. Status: {output_response.status_code}")
                                logger.warning(f"Error Response: {error_text}")
                                logger.info(f"============================================")

                                # Check if this is a "task not found" error
                                if ("no task table entry" in error_text.lower() or
                                    "invalid route" in error_text.lower() or
                                    output_response.status_code == 404):
                                    return f"Task not found on ClusterODM (UUID: {self.uuid})\n\nThis task may have been processed on a different node or removed.\nNo console output is available."
                                elif output_response.status_code == 401 or output_response.status_code == 403:
                                    return f"Authentication failed when retrieving output for task {self.uuid}\n\nThis may indicate a JWT token issue.\nError: {error_text}"
                                else:
                                    # For other errors, provide helpful debugging info
                                    return f"Unable to retrieve output for task {self.uuid}\n\nHTTP Status: {output_response.status_code}\nError: {error_text}\n\nThis task may be in an error state or not accessible."

                        except requests.exceptions.ConnectionError as e:
                            logger.warning(f"Connection error while retrieving task output: {str(e)}")
                            logger.info(f"============================================")
                            return f"Unable to connect to ClusterODM for task output (UUID: {self.uuid})\n\nConnection Error: {str(e)}\n\nClusterODM may be unreachable or the task may not exist."
                        except requests.exceptions.Timeout as e:
                            logger.warning(f"Timeout while retrieving task output: {str(e)}")
                            logger.info(f"============================================")
                            return f"Timeout retrieving output for task {self.uuid}\n\nThe request timed out after {self.timeout} seconds.\nClusterODM may be slow or unresponsive."
                        except Exception as e:
                            logger.warning(f"Exception while retrieving task output: {str(e)}")
                            logger.info(f"============================================")
                            return f"Error retrieving output for task {self.uuid}\n\nException: {str(e)}\n\nPlease check the logs for more details."

                def download_zip(self, destination, progress_callback=None, parallel_downloads=1):
                        tokens_to_try = []
                        if self.auth_token:
                            tokens_to_try.append(self.auth_token)
                        if self._wrapper and self._wrapper.token and self._wrapper.token not in tokens_to_try:
                            tokens_to_try.append(self._wrapper.token)
                        tokens_to_try.append(None)  # final attempt without token for backwards compat

                        last_error = None

                        for idx, token in enumerate(tokens_to_try):
                            params = {}
                            if token:
                                params['token'] = token

                            zip_endpoint = f"{self.base_url}/task/{self.uuid}/download/all.zip"
                            if params:
                                zip_endpoint += "?" + urlencode(params)

                            if token:
                                if token == self.auth_token and token == getattr(self._wrapper, 'jwt_token', None):
                                    token_label = "jwt"
                                elif self._wrapper and token == getattr(self._wrapper, 'token', None):
                                    token_label = "node"
                                else:
                                    token_label = "custom"
                            else:
                                token_label = "none"
                            attempt_info = f"[attempt {idx + 1}/{len(tokens_to_try)} | token={token_label}]"
                            logger.info(f"[JWTNodeWrapper] Downloading task assets from {zip_endpoint} {attempt_info}")

                            try:
                                with requests.get(zip_endpoint, stream=True, timeout=self.timeout) as response:
                                    if response.status_code != 200:
                                        error_text = response.text[:500]
                                        logger.warning(f"[JWTNodeWrapper] Download attempt failed for {self.uuid} {attempt_info}: "
                                                        f"{response.status_code} - {error_text}")

                                        # If we have more tokens to try, continue loop
                                        if idx + 1 < len(tokens_to_try):
                                            last_error = (response.status_code, error_text)
                                            continue

                                        raise NodeServerError(
                                            f"ClusterODM download failed with status {response.status_code}: {error_text}"
                                        )

                                    total_size = int(response.headers.get('content-length', 0))
                                    downloaded = 0
                                    chunk_size = 1024 * 1024

                                    os.makedirs(destination, exist_ok=True)
                                    temp_path = os.path.join(destination, f"{self.uuid}_all.zip.download")
                                    final_path = os.path.join(destination, f"{self.uuid}_all.zip")

                                    with open(temp_path, 'wb') as file_handle:
                                        for chunk in response.iter_content(chunk_size=chunk_size):
                                            if not chunk:
                                                continue
                                            file_handle.write(chunk)
                                            downloaded += len(chunk)

                                            if progress_callback:
                                                try:
                                                    if total_size > 0:
                                                        progress = (downloaded / total_size) * 100.0
                                                    else:
                                                        progress = 0.0
                                                    progress_callback(progress)
                                                except Exception as progress_error:
                                                    logger.debug(f"[JWTNodeWrapper] Progress callback raised: {progress_error}")

                                    os.replace(temp_path, final_path)
                                    logger.info(f"[JWTNodeWrapper] Assets downloaded for task {self.uuid} -> {final_path}")
                                    return final_path
                            except requests.exceptions.RequestException as e:
                                logger.warning(f"[JWTNodeWrapper] Request error downloading assets {attempt_info}: {str(e)}")
                                last_error = (None, str(e))
                                if idx + 1 < len(tokens_to_try):
                                    continue
                                raise NodeServerError(f"Error downloading assets from ClusterODM: {str(e)}")
                            except NodeServerError:
                                raise
                            except Exception as e:
                                logger.warning(f"[JWTNodeWrapper] Unexpected error downloading assets {attempt_info}: {str(e)}")
                                last_error = (None, str(e))
                                if idx + 1 < len(tokens_to_try):
                                    continue
                                raise

                        if last_error:
                            status, message = last_error
                            if status is not None:
                                raise NodeServerError(f"ClusterODM download failed with status {status}: {message}")
                            else:
                                raise NodeServerError(f"ClusterODM download failed: {message}")

                def restart(self, options=None):
                        # For task restart, we need to make a POST request to restart endpoint
                        restart_endpoint = f"{self.base_url}/task/{self.uuid}/restart"
                        params = {}
                        if self.auth_token:
                            params['token'] = self.auth_token
                        if params:
                            restart_endpoint += "?" + urlencode(params)

                        data = {}
                        if options:
                            import json
                            data['options'] = json.dumps([{'name': k, 'value': v} for k, v in options.items()])

                        try:
                            restart_response = requests.post(restart_endpoint, data=data, timeout=self.timeout)
                            if restart_response.status_code == 200:
                                return restart_response.json()
                            else:
                                error_msg = f"Failed to restart task: {restart_response.status_code} - {restart_response.text}"
                                logger.error(error_msg)
                                raise Exception(error_msg)
                        except Exception as e:
                            logger.error(f"Error restarting task with JWT token: {str(e)}")
                            raise

                def remove(self):
                        # For task removal, we need to make a POST request to remove endpoint
                        remove_endpoint = f"{self.base_url}/task/{self.uuid}/remove"
                        params = {}
                        if self.auth_token:
                            params['token'] = self.auth_token
                        if params:
                            remove_endpoint += "?" + urlencode(params)

                        logger.info(f"=== HTTP REQUEST DETAILS (Task Remove) ===")
                        logger.info(f"Method: POST")
                        logger.info(f"URL: {remove_endpoint}")
                        logger.info(f"Query Parameters: {params}")
                        logger.info(f"==========================================")

                        try:
                            remove_response = requests.post(remove_endpoint, timeout=self.timeout)

                            logger.info(f"=== HTTP RESPONSE DETAILS (Task Remove) ===")
                            logger.info(f"Status Code: {remove_response.status_code}")
                            logger.info(f"Response Headers: {dict(remove_response.headers)}")
                            logger.info(f"Response Content Length: {len(remove_response.content)} bytes")

                            if remove_response.status_code == 200:
                                try:
                                    result = remove_response.json()
                                    logger.info(f"Task removal response: {result}")
                                    logger.info(f"============================================")
                                    return result
                                except ValueError:
                                    # Some removal endpoints may return plain text instead of JSON
                                    logger.info(f"Task removal response (text): {remove_response.text}")
                                    logger.info(f"============================================")
                                    return {"success": True, "message": remove_response.text}
                            else:
                                error_text = remove_response.text
                                logger.warning(f"Failed to remove task from ClusterODM. Status: {remove_response.status_code}")
                                logger.warning(f"Error Response: {error_text}")

                                # Check if this is a "task not found" error - if so, consider it successful
                                # since the task doesn't exist on ClusterODM anyway
                                if ("no task table entry" in error_text.lower() or
                                    "invalid route" in error_text.lower() or
                                    remove_response.status_code == 404):
                                    logger.info(f"Task {self.uuid} not found on ClusterODM, considering removal successful")
                                    logger.info(f"============================================")
                                    return {"success": True, "message": "Task not found on ClusterODM, removed from WebODM"}
                                else:
                                    # For other errors, still log but don't fail the removal
                                    logger.warning(f"ClusterODM removal failed but continuing with WebODM cleanup")
                                    logger.info(f"============================================")
                                    return {"success": True, "message": f"WebODM cleanup completed (ClusterODM error: {error_text})"}
                        except requests.exceptions.RequestException as e:
                            logger.warning(f"Request error when removing task from ClusterODM: {str(e)}")
                            logger.warning(f"ClusterODM may be unreachable, continuing with WebODM cleanup")
                            logger.info(f"============================================")
                            return {"success": True, "message": f"WebODM cleanup completed (ClusterODM unreachable: {str(e)})"}
                        except Exception as e:
                            logger.warning(f"Exception while removing task from ClusterODM: {str(e)}")
                            logger.warning(f"Continuing with WebODM cleanup despite ClusterODM error")
                            logger.info(f"============================================")
                            return {"success": True, "message": f"WebODM cleanup completed (ClusterODM error: {str(e)})"}

                def cancel(self):
                        if self._wrapper:
                            return self._wrapper.cancel_task(self.uuid)

                        # Fallback path if wrapper reference isn't available
                        cancel_endpoint = f"{self.base_url}/task/{self.uuid}/cancel"
                        params = {}
                        if self.auth_token:
                            params['token'] = self.auth_token
                        if params:
                            cancel_endpoint += "?" + urlencode(params)

                        logger.info(f"=== HTTP REQUEST DETAILS (Task Cancel) ===")
                        logger.info(f"Method: POST")
                        logger.info(f"URL: {cancel_endpoint}")
                        logger.info(f"Query Parameters: {params}")
                        logger.info(f"==========================================")

                        try:
                            cancel_response = requests.post(cancel_endpoint, timeout=self.timeout)

                            logger.info(f"=== HTTP RESPONSE DETAILS (Task Cancel) ===")
                            logger.info(f"Status Code: {cancel_response.status_code}")
                            logger.info(f"Response Headers: {dict(cancel_response.headers)}")
                            logger.info(f"Response Content Length: {len(cancel_response.content)} bytes")

                            if cancel_response.status_code == 200:
                                try:
                                    result = cancel_response.json()
                                    logger.info(f"Task cancel response: {result}")
                                    logger.info(f"============================================")
                                    return result
                                except ValueError:
                                    logger.info(f"Task cancel response (text): {cancel_response.text}")
                                    logger.info(f"============================================")
                                    return {"success": True, "message": cancel_response.text}
                            else:
                                error_text = cancel_response.text
                                logger.warning(f"Failed to cancel task on ClusterODM. Status: {cancel_response.status_code}")
                                logger.warning(f"Error Response: {error_text}")

                                if ("no task table entry" in error_text.lower() or
                                    "invalid route" in error_text.lower() or
                                    cancel_response.status_code == 404):
                                    logger.info(f"Task {self.uuid} not found on ClusterODM, considering cancel successful")
                                    logger.info(f"============================================")
                                    return {"success": True, "message": "Task not found on ClusterODM, considered canceled"}

                                logger.info(f"============================================")
                                return {"success": False, "message": f"ClusterODM cancel failed: {error_text}"}
                        except requests.exceptions.RequestException as e:
                            logger.warning(f"Request error when canceling task from ClusterODM: {str(e)}")
                            logger.warning(f"Continuing with WebODM cancel despite ClusterODM error")
                            logger.info(f"============================================")
                            return {"success": False, "message": f"ClusterODM cancel request failed: {str(e)}"}
                        except Exception as e:
                            logger.warning(f"Exception while canceling task from ClusterODM: {str(e)}")
                            logger.warning(f"Continuing with WebODM cancel despite ClusterODM error")
                            logger.info(f"============================================")
                            return {"success": False, "message": f"ClusterODM cancel error: {str(e)}"}
                
                return TaskWrapper(uuid, task_info_data, self, self.auth_token, self.timeout)
                
        except Exception as e:
            logger.error(f"Error getting task info with JWT token: {str(e)}")
            # Fall back to regular node for compatibility
            return self._node.get_task(uuid)
    
    def cancel_task(self, uuid):
        """
        Cancel a task directly using the JWT-enabled endpoint.
        """
        cancel_endpoint = f"{self.base_url}/task/{uuid}/cancel"
        params = {}
        if self.auth_token:
            params['token'] = self.auth_token
        if params:
            cancel_endpoint += "?" + urlencode(params)

        logger.info(f"=== HTTP REQUEST DETAILS (Task Cancel - Direct) ===")
        logger.info(f"Method: POST")
        logger.info(f"URL: {cancel_endpoint}")
        logger.info(f"Query Parameters: {params}")
        logger.info(f"==========================================")

        try:
            cancel_response = requests.post(cancel_endpoint, timeout=self.timeout)

            logger.info(f"=== HTTP RESPONSE DETAILS (Task Cancel - Direct) ===")
            logger.info(f"Status Code: {cancel_response.status_code}")
            logger.info(f"Response Headers: {dict(cancel_response.headers)}")
            logger.info(f"Response Content Length: {len(cancel_response.content)} bytes")

            if cancel_response.status_code == 200:
                try:
                    result = cancel_response.json()
                    logger.info(f"Task cancel response: {result}")
                    logger.info(f"============================================")
                    return result
                except ValueError:
                    logger.info(f"Task cancel response (text): {cancel_response.text}")
                    logger.info(f"============================================")
                    return {"success": True, "message": cancel_response.text}
            else:
                error_text = cancel_response.text
                logger.warning(f"Failed to cancel task on ClusterODM. Status: {cancel_response.status_code}")
                logger.warning(f"Error Response: {error_text}")

                if ("no task table entry" in error_text.lower() or
                    "invalid route" in error_text.lower() or
                    cancel_response.status_code == 404):
                    logger.info(f"Task {uuid} not found on ClusterODM, considering cancel successful")
                    logger.info(f"============================================")
                    return {"success": True, "message": "Task not found on ClusterODM, considered canceled"}

                logger.info(f"============================================")
                return {"success": False, "message": f"ClusterODM cancel failed: {error_text}"}
        except requests.exceptions.RequestException as e:
            logger.warning(f"Request error when canceling task from ClusterODM: {str(e)}")
            logger.warning(f"Continuing with WebODM cancel despite ClusterODM error")
            logger.info(f"============================================")
            return {"success": False, "message": f"ClusterODM cancel request failed: {str(e)}"}
        except Exception as e:
            logger.warning(f"Exception while canceling task from ClusterODM: {str(e)}")
            logger.warning(f"Continuing with WebODM cancel despite ClusterODM error")
            logger.info(f"============================================")
            return {"success": False, "message": f"ClusterODM cancel error: {str(e)}"}
    
    def __getattr__(self, name):
        """
        Delegate all other method calls to the underlying Node instance.
        
        This allows the wrapper to maintain compatibility with the pyodm Node interface
        for operations that don't require JWT token support.
        """
        return getattr(self._node, name)
