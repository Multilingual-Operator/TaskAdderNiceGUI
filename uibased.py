#!/usr/bin/env python3
import asyncio
import logging
import os
import json
from datetime import datetime
from idlelib.window import add_windows_to_menu
from typing import List, Dict, Any, Optional, Tuple
from difflib import SequenceMatcher

# Import NiceGUI components
from nicegui import Client, app, ui, context

# Import Playwright
from playwright.async_api import async_playwright, Playwright, Page

# Constants
ACTION_TYPES = ["click", "type", "select", "ignore", "finish_task"]
DEFAULT_URL = "https://www.digikala.com/"
ANNOTATION_DATA_DIR = "annotation_data"
with open("mouse_control.js") as f:
    mouse_control_js = f.read()



class AnnotationFramework:
    def __init__(self):
        self.playwright: Optional[Playwright] = None
        self.browser = None
        self.context = None
        self.page: Optional[Page] = None
        self.logger = self._setup_logger()

    def _setup_logger(self):
        """Setup logging"""
        logger = logging.getLogger("AnnotationFramework")
        logger.setLevel(logging.INFO)
        if not logger.hasHandlers(): # Avoid adding multiple handlers on reload
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        return logger

    async def start(self, website=DEFAULT_URL):
        """Start the browser and navigate to the specified website"""
        try:
            self.playwright = await async_playwright().start()
            # Consider launching in headed mode for the user to see
            self.browser = await self.playwright.chromium.launch(headless=False)
            self.context = await self.browser.new_context()
            self.page = await self.context.new_page()

            # Navigate to website
            await self.page.goto(website)
            self.logger.info(f"Navigated to {website}")
            return self.page
        except Exception as e:
            self.logger.error(f"Error starting Playwright: {e}")
            await self.stop() # Clean up if start fails partially
            raise # Re-raise the exception

    async def stop(self):
        """Stop the browser"""
        self.logger.info("Stopping Playwright...")
        if self.page and not self.page.is_closed():
             try:
                 await self.page.close()
             except Exception as e:
                 self.logger.warning(f"Error closing page: {e}")
        if self.context:
            try:
                await self.context.close()
            except Exception as e:
                self.logger.warning(f"Error closing context: {e}")
        if self.browser:
            try:
                await self.browser.close()
            except Exception as e:
                self.logger.warning(f"Error closing browser: {e}")
        if self.playwright:
            try:
                await self.playwright.stop()
            except Exception as e:
                self.logger.warning(f"Error stopping Playwright: {e}")

        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        self.logger.info("Playwright stopped")

    async def setup_element_tracking(self):
        """Setup browser to track selected elements"""
        if not self.page:
            self.logger.error("Error: No active page for element tracking setup")
            return

        try:
            await self.page.evaluate(mouse_control_js)
            # Expose Python function to be called from JS
            # Use a unique name or check if already exposed if page reloads cause issues
            self.logger.info("Element tracking script injected and callback exposed.")
        except Exception as e:
            self.logger.error(f"Error setting up element tracking: {e}")
            raise

    async def set_annotation_mode(self, enabled: bool):
         if not self.page: return
         try:
             await self.page.evaluate(f"window.setAnnotationMode({str(enabled).lower()})")
             self.logger.info(f"Annotation mode set to {enabled} in browser.")
         except Exception as e:
             self.logger.error(f"Error setting annotation mode in browser: {e}")

    async def unlock_element_in_browser(self):
        if not self.page: return
        try:
            await self.page.evaluate("() => window.unlockElement()")
            self.logger.info("Requested element unlock in browser.")
        except Exception as e:
            self.logger.error(f"Error unlocking element in browser: {e}")

    async def get_selected_element_data_from_browser(self) -> Optional[Dict]:
         if not self.page: return None
         try:
             element_data = await self.page.evaluate("() => window._selectedElement")
             return element_data
         except Exception as e:
             self.logger.error(f"Error getting selected element data from browser: {e}")
             return None

    async def _find_element(self, element_data: Dict):
        """Helper to find element using various strategies"""
        if not self.page: raise Exception("Playwright page not available")

        # Prefer XPath if available and valid
        xpath = element_data.get('xpath')
        if xpath:
            try:
                # Check if XPath uniquely identifies the element
                count = await self.page.locator(f"xpath={xpath}").count()
                if count == 1:
                    return self.page.locator(f"xpath={xpath}")
                else:
                     self.logger.warning(f"XPath '{xpath}' matched {count} elements, expected 1. Trying other methods.")
            except Exception as e:
                 self.logger.warning(f"XPath '{xpath}' failed: {e}. Trying other methods.")

        # Try ID if available
        element_id = element_data.get('id')
        if element_id:
            selector = f"#{element_id}"
            try:
                 count = await self.page.locator(selector).count()
                 if count == 1:
                     return self.page.locator(selector)
                 else:
                     self.logger.warning(f"ID selector '{selector}' matched {count} elements. Trying other methods.")
            except Exception as e:
                 self.logger.warning(f"ID selector '{selector}' failed: {e}. Trying other methods.")

        # If nothing worked
        error_msg = f"Could not reliably locate element: {element_data}"
        self.logger.error(error_msg)
        raise Exception(error_msg)


    async def click_element(self, element_data: Dict):
        """Click an element based on element data"""
        if not self.page:
            self.logger.error("No page available to click")
            return False
        try:
            element_locator = await self._find_element(element_data)
            await element_locator.click(timeout=5000) # Add timeout
            self.logger.info(f"Clicked element: {element_data.get('tagName')}")
            return True
        except Exception as e:
            self.logger.error(f"Error clicking element ({element_data.get('xpath', 'N/A')}): {e}")
            return False

    async def type_text(self, element_data: Dict, text: str):
        """Type text into an element based on element data"""
        if not self.page:
            self.logger.error("No page available to type")
            return False
        try:
            element_locator = await self._find_element(element_data)
            await element_locator.fill(text, timeout=5000) # Use fill for inputs, add timeout
            self.logger.info(f"Typed '{text}' into element: {element_data.get('tagName')}")
            return True
        except Exception as e:
            self.logger.error(f"Error typing into element ({element_data.get('xpath', 'N/A')}): {e}")
            return False

    async def select_option(self, element_data: Dict, text: str):
        """Type text into an element based on element data"""
        if not self.page:
            self.logger.error("No page available to select")
            return False
        try:
            element_locator = await self._find_element(element_data)

            best_option = [-1, "", -1]
            for i in range(await element_locator.locator("option").count()):
                option = await element_locator.locator("option").nth(i).inner_text()
                similarity = SequenceMatcher(None, option, text).ratio()
                if similarity > best_option[2]:
                    best_option = [i, option, similarity]
            await element_locator.select_option(index=best_option[0], timeout=10000)
            self.logger.info(f"selected '{text}' into element: {element_data.get('tagName')}")
            return True
        except Exception as e:
            self.logger.error(f"Error selection option into element ({element_data.get('xpath', 'N/A')}): {e}")
            return False

# --- NiceGUI Application Class ---
class AnnotationUI:
    def __init__(self):
        self.framework = AnnotationFramework()
        self.log = None # Placeholder for ui.log
        self.status_label = None # Placeholder for status ui.label

        # --- State Variables ---
        self.url: str = DEFAULT_URL
        self.task_description: str = ""
        self.selected_action: str = ACTION_TYPES[0]
        self.action_value: str = ""
        self.status_text: str = "Ready. Enter URL and Launch Browser."
        self.current_log_messages: List[str] = ["Annotation Console initialized."]

        self.selected_element: Optional[Dict] = None
        self.element_tracking_active: bool = False
        self.task_started: bool = False
        self.browser_launched: bool = False
        self.task_actions: List[Dict] = []

        # --- Build UI ---
        self.setup_ui()
        self.setup_api_endpoints()


    def add_to_log(self, message: str):
        """Add message to the NiceGUI log"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {message}"
        print(log_entry) # Also print to console for debugging
        self.current_log_messages.append(log_entry)
        if self.log:
            self.log.push(log_entry) # Push to NiceGUI log component

    def update_status(self, message: str):
        """Update the status label"""
        self.status_text = message
        if self.status_label:
            self.status_label.set_text(message)

    # --- Async Handlers ---
    async def launch_browser(self):
        """Launch Playwright browser and navigate"""
        if not self.url.startswith(('http://', 'https://')):
            self.url = f"https://{self.url}"
            ui.notify(f"Assuming HTTPS. URL updated to: {self.url}", type='info')
            # Need to find the input element and update its value if binding isn't two-way immediately
            # Or rely on the user seeing the notification and the bound variable being updated internally.

        self.update_status(f"Launching browser for {self.url}...")
        self.add_to_log(f"Attempting to launch browser at: {self.url}")
        # Disable launch button immediately
        self.launch_button.disable()
        self.url_input.disable()

        try:
            await self.framework.start(website=self.url)
            if not self.framework.page:
                 raise Exception("Framework started but page object is missing.")

            # Setup element tracking *after* page is loaded
            await self.framework.setup_element_tracking()

            self.add_to_log(f"Browser launched successfully for {self.url}")
            self.browser_launched = True
            # Enable task start, disable URL section
            self.task_input.enable()
            self.task_button.enable()
            self.update_status("Browser ready. Describe and start your task.")

        except Exception as e:
            self.add_to_log(f"Error launching browser: {e}")
            self.update_status(f"Browser launch failed! Check URL and console logs. Error: {e}")
            await self.framework.stop() # Ensure cleanup
            self.browser_launched = False
            # Re-enable launch button on failure
            self.launch_button.enable()
            self.url_input.enable()


    async def start_task(self):
        """Start the task annotation process"""
        await self.framework.setup_element_tracking()
        if not self.browser_launched or not self.framework.page:
            ui.notify("Browser not launched successfully.", type='negative')
            return
        if not self.task_description:
            ui.notify("Please enter a task description.", type='warning')
            return

        self.task_started = True
        self.task_actions = []
        self.add_to_log(f"Task started: {self.task_description}")

        # Enable action recording section, disable task start section
        self.value_input.disable()
        self.task_input.disable()
        self.task_button.disable()

        # Enable element tracking in browser via JS function
        self.element_tracking_active = True
        await self.framework.set_annotation_mode(True)

        self.update_status("Task in progress. Click elements in browser and record actions.")

    async def handle_element_selection(self):
        """Fetch selected element data and update UI"""
        print("Element selection handler called")
        if not self.element_tracking_active or not self.framework.page:
            print("Element tracking inactive or no page available")
            return  # Don't process if tracking isn't active

        try:
            # Don't rely on UI-specific context here
            element_data = await self.framework.get_selected_element_data_from_browser()

            # Use a proper NiceGUI context by using the main container
            with self.main_container:  # Assuming you have a main_container defined in your UI
                self.add_to_log("Element selection detected in browser. Fetching data...")

                if element_data:
                    self.selected_element = element_data
                    tag = element_data.get('tagName', 'Unknown')
                    text = element_data.get('textContent', '')[:50]  # Show first 50 chars
                    xpath = element_data.get('xpath', 'N/A')
                    self.add_to_log(f"Selected element: <{tag}> - '{text}' (XPath: {xpath})")
                    self.update_status(f"Element locked: <{tag}>. Choose action/value or 'ignore'.")

                    # Enable UI elements directly through NiceGUI's methods
                    self.record_button.enabled = True
                    self.action_select.enabled = True
                    self.value_input.enabled = True

                    if tag == "SELECT":
                        # Fetch dropdown options
                        self.selected_element_options = await self.get_dropdown_options(element_data)
                        if self.selected_element_options:
                            self.add_to_log(f"Found {len(self.selected_element_options)} dropdown options")
                            self.create_options_dropdown()

                        self.action_select.value = "select"
                        self.selected_action = "select"
                    elif tag == "INPUT" or tag == "TEXTAREA":
                        # For input fields and textareas, we typically use "type" action
                        self.action_select.value = "type"
                        self.selected_action = "type"
                    elif tag in ["BUTTON", "A", "DIV", "SPAN", "LI", "IMG"]:
                        # For clickable elements like buttons, links, and other interactive elements
                        self.action_select.value = "click"
                        self.selected_action = "click"

                    # Auto-populate value if applicable
                    if self.selected_action == "type" and tag in ["INPUT", "TEXTAREA"]:
                        self.value_input.value = element_data.get('value', '')
                    else:
                        self.value_input.value = ""
                else:
                    self.add_to_log("Failed to retrieve selected element data from browser.")
                    self.update_status("Error fetching element data. Try selecting again.")

                    # Disable UI elements directly through NiceGUI's methods
                    self.record_button.enabled = False
                    self.action_select.enabled = False
                    self.value_input.enabled = False
        except Exception as e:
            print(f"Error in handle_element_selection: {e}")

    async def get_dropdown_options(self, element_data):
        """Fetch options from a dropdown element using Python and browser automation"""
        try:
            # Extract the xpath from element_data
            xpath = element_data.get('xpath')
            if not xpath:
                self.add_to_log("Cannot retrieve dropdown options: No XPath available")
                return []

            # Get all option elements within the SELECT
            options_locator = self.framework.page.locator(f"xpath={xpath}//option")
            options_count = await options_locator.count()

            options = []
            # Extract data from each option
            for i in range(options_count):
                option = options_locator.nth(i)

                # Get properties of each option
                value = await option.get_attribute("value") or ""
                text = await option.text_content() or ""

                options.append({
                    'value': value,
                    'text': text.strip()
                })

            return options
        except Exception as e:
            print(f"Error getting dropdown options: {e}")
            self.add_to_log(f"Could not retrieve dropdown options: {str(e)}")
            return []

    def create_options_dropdown(self):
        """Create a proper dropdown for selecting options from the page's SELECT element"""
        try:
            self.add_to_log("try to make dropdown")
            # First remove the hidden class to make the container visible
            self.options_dropdown_container.classes("w-full p-1 mt-1")
            self.options_dropdown_container.clear()
            # Create the select dropdown
            with self.options_dropdown_container:
                # Create the dropdown select
                option_items = [f"{opt['text']}" for opt in self.selected_element_options]
                print(option_items)
                # Create the dropdown with options
                self.options_select = ui.select(
                    options=option_items,
                    value=None,
                    on_change=self.handle_option_selection
                ).classes('w-full').props('use-input filter persistent')

                # Add a confirmation button
                ui.button("Confirm Selected Option", on_click=self.confirm_option_selection).classes('mt-1')

                # Force UI update
                ui.update()
        except Exception as e:
            print(f"Error creating options dropdown: {e}")
            self.add_to_log(f"Could not create dropdown selector: {str(e)}")

    def handle_option_selection(self, e):
        """Handle when user selects an option from the dropdown"""
        try:
            # Find the selected option in our list
            selected_text = e.value
            for i, opt in enumerate(self.selected_element_options):
                if f"{opt['text']}" == selected_text:
                    # Preview the selection
                    self.add_to_log(f"Selected option: {opt['text']}")
                    self.current_selected_option = opt
                    break
        except Exception as e:
            print(f"Error handling option selection: {e}")
            self.add_to_log(f"Error selecting option: {str(e)}")

    def confirm_option_selection(self):
        """Confirm and apply the selected option"""
        try:
            if self.current_selected_option:
                # Update the value input with the selected option value
                self.value_input.value = self.current_selected_option['text']
                self.action_value = self.current_selected_option['text']

                # Update UI
                self.add_to_log(f"Confirmed option: {self.current_selected_option['text']}")
                self.update_status(f"Option selected: {self.current_selected_option['text']}")
        except Exception as e:
            print(f"Error confirming option selection: {e}")
            self.add_to_log(f"Error applying selection: {str(e)}")

    async def record_action(self):
        """Record the selected action and value for the selected element."""
        action_type = self.selected_action
        action_value = self.action_value # Get value from bound variable

        # --- Handle IGNORE action ---
        if action_type == "ignore":
            if self.selected_element:
                self.add_to_log("Ignoring selected element.")
                # Unlock element in browser
                await self.framework.unlock_element_in_browser()
                self.selected_element = None
                self.update_status("Element ignored. Select another element.")
                # Disable record button until next selection? Or keep enabled?
                self.record_button.disable()
                self.action_select.disable()
                self.value_input.disable()
            else:
                ui.notify("No element is currently selected to ignore.", type='warning')
            return # Stop processing here for ignore action

        # --- Handle FINISH_TASK action ---
        if action_type == "finish_task":
            await self.finish_task()
            return # Stop processing here for finish action

        # --- Handle other actions (click, type, select) ---
        if not self.selected_element:
            ui.notify("Please select an element in the browser first.", type='warning')
            return

        await self.framework.unlock_element_in_browser()
        await self.framework.set_annotation_mode(False)
        await asyncio.sleep(0.1)
        # --- Create and Store Action ---
        action_record = {
            "type": action_type,
            "value": action_value,
            "element": self.selected_element, # Store details of the element acted upon
            "timestamp": datetime.now().isoformat(),
        }
        self.task_actions.append(action_record)
        log_msg = f"Recorded: {action_type}"
        if action_value: log_msg += f" - Value: '{action_value}'"
        log_msg += f" on <{self.selected_element.get('tagName','?')}>"
        self.add_to_log(log_msg)

        # --- Execute Action in Browser (Optional but Recommended) ---
        action_executed = False
        if action_type == "click":
            action_executed = await self.framework.click_element(self.selected_element)
        elif action_type == "type":
            action_executed = await self.framework.type_text(self.selected_element, action_value)
        elif action_type == "select":
             action_executed = await self.framework.select_option(self.selected_element, action_value)
        else:
             # Should not happen if action types are validated
             self.add_to_log(f"Warning: Unknown action type '{action_type}' encountered during execution.")
             action_executed = True # Treat as success to proceed


        # --- Post-Action Cleanup ---
        await self.framework.set_annotation_mode(True)
        # Clear value input and selected element state
        self.action_value = ""
        self.value_input.update() # Clear the NiceGUI input field
        self.selected_element = None

        if action_executed:
            self.update_status("Action recorded and executed. Select next element.")
        else:
             self.update_status("Action recorded but FAILED execution. Select next element.")
             ui.notify(f"Execution failed for {action_type}. Check browser/logs.", type='negative')

        # Disable record button until next selection?
        self.record_button.disable()
        self.action_select.disable()
        self.value_input.disable()

    async def finish_task(self):
        """Finalize the task and save data."""
        if not self.task_started:
            ui.notify("No task is currently active.", type='warning')
            return

        self.add_to_log("Finishing task...")
        self.task_started = False
        self.element_tracking_active = False

        # Disable annotation mode in browser and ensure element is unlocked
        if self.framework.page:
            await self.framework.set_annotation_mode(False)
            # Unlock just in case it was somehow locked without Python knowing
            await self.framework.unlock_element_in_browser()

        # Save the task data
        try:
            filename = await self.save_task_data()
            self.add_to_log(f"Task data saved successfully to {filename}")
            ui.notify(f"Task data saved to {filename}", type='positive')
        except Exception as e:
             self.add_to_log(f"Error saving task data: {e}")
             ui.notify(f"Failed to save task data: {e}", type='negative')


        # Reset UI state for a new task (keep browser open)
        self.selected_element = None
        self.task_actions = []
        self.action_select.disable()
        self.value_input.set_value("") # Clear value
        self.value_input.disable()
        self.record_button.disable()

        self.task_input.enable()
        self.task_button.enable() # Allow starting a new task
        self.task_description = "" # Clear description
        self.task_input.update()

        self.update_status("Task finished and saved. Ready for new task or close browser.")


    async def save_task_data(self):
        """Save task data to JSON file"""
        os.makedirs(ANNOTATION_DATA_DIR, exist_ok=True)

        task_data = {
            "task_description": self.task_description,
            "website": self.url,
            "timestamp": datetime.now().isoformat(),
            "actions": self.task_actions
        }

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        # Sanitize task description for filename (optional)
        safe_desc = "".join(c for c in self.task_description if c.isalnum() or c in (' ', '_')).rstrip()[:30]
        filename = os.path.join(ANNOTATION_DATA_DIR, f"task_{timestamp}_{safe_desc}.json")

        with open(filename, "w") as f:
            json.dump(task_data, f, indent=4) # Use indent for readability

        return filename

    async def cleanup(self):
        """Called when the NiceGUI app is shutting down"""
        self.add_to_log("Application shutting down...")
        await self.framework.stop()
        self.add_to_log("Cleanup finished.")


    def on_action_select(self, e):
        # Update the selected action
        self.selected_action = e.value
        if self.selected_action == "select":
            self.create_options_dropdown()
        else:
            self.options_dropdown_container.clear()

    # --- UI Setup Method ---
    def setup_ui(self):
        self.main_container =ui.column().classes('h-screen w-full fixed left-0 top-0 bg-gray-100 overflow-auto p-1')
        # Change max-w-2/3 to w-2/3 to set the exact width
        with self.main_container:
            # URL Section
            with ui.column().classes('w-full mb-1'):
                # Create a row to hold the URL input and launch button side by side
                with ui.row().classes('w-full items-center'):
                    self.url_input = ui.input('Website URL', placeholder='e.g., https://www.example.com',
                                              value=self.url, on_change=lambda e: setattr(self, 'url', e.value)) \
                        .props('dense outlined').classes('flex-grow')

                    # Position the launch button next to the input field
                    self.launch_button = ui.button('', on_click=self.launch_browser) \
                        .props('icon=launch').classes('bg-primary text-white ml-1')

            # Task Description Section
            with ui.column().classes('w-full mb-1'):
                # Create a row to hold the task input and start button side by side
                with ui.row().classes('w-full items-center align-top'):
                    # Replace input with textarea for multi-line support
                    self.task_input = ui.textarea('Task Description', placeholder='e.g., Search for product X',
                                               value=self.task_description,
                                               on_change=lambda e: setattr(self, 'task_description', e.value)) \
                        .props('dense outlined rows=2').classes('flex-grow').bind_enabled_from(self,
                                                                                        'browser_launched')

                    # Position the task button next to the input field (align to top)
                    self.task_button = ui.button('', on_click=self.start_task) \
                        .props('icon=play_arrow').classes('bg-positive text-white ml-1 self-start mt-4') \
                        .bind_enabled_from(self, 'browser_launched')

            # Action Recording Section
            with ui.column().classes('w-full mb-1'):
                self.action_select = ui.select(ACTION_TYPES, label='Action', value=self.selected_action,
                                               on_change=self.on_action_select) \
                    .props('dense outlined').classes('w-full')

                self.value_input = ui.input('Value (if applicable)', value=self.action_value,
                                            on_change=lambda e: setattr(self, 'action_value', e.value)) \
                    .props('dense outlined').classes('w-full')


                # Create options dropdown container (initially hidden)
                with ui.element('div').classes('w-full mt-1') as self.options_dropdown_container:
                    pass

                self.record_button = ui.button('Record Action', on_click=self.record_action) \
                    .props('icon=radio_button_checked').classes('bg-accent text-white w-full')
                self.record_button.disable()  # Initially disabled
                self.action_select.disable()
                self.value_input.disable()

            # Log Output Section
            with ui.column().classes('w-full'):
                # Use ui.log for auto-scrolling log display
                self.log = ui.log(max_lines=50).classes('w-full h-64 bg-gray-100 rounded p-2 font-mono text-sm')
                # Initialize log with existing messages
                for msg in self.current_log_messages:
                    self.log.push(msg)

            # Status Bar (at the bottom of the column)
            with ui.row().classes('w-full mt-auto bg-gray-200 p-1 rounded-lg items-center'):
                ui.icon('info').classes('text-primary mr-1')
                self.status_label = ui.label(self.status_text).classes('text-sm')

        # --- Register App Shutdown Handler ---
        # Use app context if available (newer NiceGUI versions)
        if hasattr(context, 'app'):
            context.app.on_shutdown(self.cleanup)
        else:  # Fallback for older versions
            app.on_shutdown(self.cleanup)

    def setup_api_endpoints(self):
        """Set up API endpoints for browser-to-Python communication"""

        @app.get('/api/notify-element-selected')
        async def notify_element_selected():
            """API endpoint that JavaScript can call when an element is selected"""
            # Directly call the handler without checking context.client.connected
            # This avoids the UI context dependency
            asyncio.create_task(self.handle_element_selection())
            return {'status': 'success'}


# --- Main Execution ---
if __name__ in {"__main__", "__mp_main__"}: # Need __mp_main__ for multiprocessing spawn
    # Create the UI instance *before* ui.run
    annotation_app = AnnotationUI()

    # Run the NiceGUI app
    # Set reload=False for this kind of app where external processes (Playwright) are managed
    # Set storage_secret for potential future use with browser storage persistence
    ui.run(title="Web Task Annotator", reload=False, port=8080, storage_secret="a_secret_key_for_storage")