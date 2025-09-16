"""
JWT Node Wrapper for ClusterODM integration

This module provides a wrapper around the pyodm Node class to add JWT token support
for ClusterODM integration with Tapis authentication.
"""

import logging
import os
from pyodm import Node
from pyodm.types import TaskStatus
from urllib.parse import urlencode
import requests

logger = logging.getLogger('app.logger')


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
        # Use HTTPS for port 443, HTTP for others
        protocol = "https" if port == 443 else "http"
        self.base_url = f"{protocol}://{hostname}:{port}"
        
        # Create underlying Node instance for fallback operations
        self._node = Node(hostname, port, token, timeout)
        
        logger.info(f"Created JWTNodeWrapper for {hostname}:{port} with JWT token")
    
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
            
            if self.jwt_token:
                params['token'] = self.jwt_token
                
            if params:
                endpoint += "?" + urlencode(params)
            
            logger.info(f"Creating task with JWT token at: {endpoint}")
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
    
    def get_task(self, uuid):
        """
        Get task with JWT token support for task info queries.
        """
        try:
            # Build the URL with JWT token for task info
            endpoint = f"{self.base_url}/task/{uuid}/info"
            params = {}
            
            if self.jwt_token:
                params['token'] = self.jwt_token
                
            if params:
                endpoint += "?" + urlencode(params)
            
            logger.info(f"=== HTTP REQUEST DETAILS (Task Info) ===")
            logger.info(f"Method: GET")
            logger.info(f"URL: {endpoint}")
            logger.info(f"Query Parameters: {params}")
            logger.info(f"Timeout: {self.timeout}s")
            logger.info(f"=========================================")
            
            # Make the request
            response = requests.get(endpoint, timeout=self.timeout)
            
            # Log detailed response information
            logger.info(f"=== HTTP RESPONSE DETAILS (Task Info) ===")
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
            logger.info(f"==========================================")
            
            if response.status_code == 200:
                task_info_data = response.json()

                # Check if response contains an error instead of task data
                if 'error' in task_info_data:
                    logger.error(f"ClusterODM returned error: {task_info_data['error']}")
                    raise NodeServerError(f"ClusterODM error: {task_info_data['error']}")

                # Ensure required fields exist to prevent KeyError in TaskInfo
                if 'uuid' not in task_info_data:
                    logger.error(f"ClusterODM response missing required 'uuid' field")
                    raise NodeServerError("ClusterODM response missing required 'uuid' field")

                # Ensure 'options' field exists to prevent KeyError
                if 'options' not in task_info_data:
                    logger.warning(f"ClusterODM response missing 'options' field, adding empty options")
                    task_info_data['options'] = []
                
                # Create a task-like object that works with WebODM
                class TaskWrapper:
                    def __init__(self, uuid, task_info_data, base_url, jwt_token, timeout):
                        self.uuid = uuid
                        self._info_data = task_info_data
                        self.base_url = base_url
                        self.jwt_token = jwt_token
                        self.timeout = timeout
                    
                    def info(self, with_output=True):
                        # Import TaskInfo here to avoid circular imports
                        from pyodm.types import TaskInfo
                        return TaskInfo(self._info_data)
                    
                    def output(self, line=0):
                        # For console output, we need to make another request
                        output_endpoint = f"{self.base_url}/task/{self.uuid}/output"
                        params = {'line': line}
                        if self.jwt_token:
                            params['token'] = self.jwt_token
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
                                logger.error(f"Failed to get task output. Status: {output_response.status_code}")
                                logger.error(f"Error Response: {error_text}")
                                logger.info(f"============================================")
                                # Return error info instead of empty string for debugging
                                return f"Error retrieving output (Status {output_response.status_code}): {error_text}"
                        except Exception as e:
                            logger.error(f"Exception while retrieving task output: {str(e)}")
                            logger.info(f"============================================")
                            return f"Exception retrieving output: {str(e)}"

                    def restart(self, options=None):
                        # For task restart, we need to make a POST request to restart endpoint
                        restart_endpoint = f"{self.base_url}/task/{self.uuid}/restart"
                        params = {}
                        if self.jwt_token:
                            params['token'] = self.jwt_token
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
                        if self.jwt_token:
                            params['token'] = self.jwt_token
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
                                logger.error(f"Failed to remove task. Status: {remove_response.status_code}")
                                logger.error(f"Error Response: {error_text}")
                                logger.info(f"============================================")
                                raise Exception(f"Failed to remove task: HTTP {remove_response.status_code} - {error_text}")
                        except requests.exceptions.RequestException as e:
                            logger.error(f"Request error when removing task: {str(e)}")
                            logger.info(f"============================================")
                            raise Exception(f"Request failed when removing task: {str(e)}")
                        except Exception as e:
                            logger.error(f"Exception while removing task: {str(e)}")
                            logger.info(f"============================================")
                            raise
                
                return TaskWrapper(uuid, task_info_data, self.base_url, self.jwt_token, self.timeout)
            else:
                error_msg = f"Failed to get task info: {response.status_code} - {response.text}"
                logger.error(error_msg)
                raise Exception(error_msg)
                
        except Exception as e:
            logger.error(f"Error getting task info with JWT token: {str(e)}")
            # Fall back to regular node for compatibility
            return self._node.get_task(uuid)
    
    def __getattr__(self, name):
        """
        Delegate all other method calls to the underlying Node instance.
        
        This allows the wrapper to maintain compatibility with the pyodm Node interface
        for operations that don't require JWT token support.
        """
        return getattr(self._node, name)