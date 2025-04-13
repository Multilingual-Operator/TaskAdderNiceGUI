() => {
    // Ensure styles/listeners are not added multiple times on reload
    if (window._annotationSetupDone) return;

    // Create a style element for highlighting
    const style = document.createElement('style');
    style.id = 'annotation-styles'; // Give it an ID
    style.textContent = `
        .annotation-highlight {
            outline: 2px solid blue !important;
            outline-offset: 1px !important;
            background-color: rgba(0, 0, 255, 0.1) !important;
            cursor: pointer !important;
        }
        .annotation-primary { /* Golden selection */
            outline: 3px solid gold !important;
            outline-offset: 2px !important;
            background-color: rgba(255, 215, 0, 0.3) !important;
        }
        .annotation-secondary { /* Green selection */
            outline: 2px solid green !important;
            outline-offset: 1px !important;
            background-color: rgba(0, 128, 0, 0.2) !important;
        }
    `;
    // Remove old style if it exists
    const oldStyle = document.getElementById('annotation-styles');
    if (oldStyle) oldStyle.remove();
    document.head.appendChild(style);

    // Global state
    window._annotationMode = false;
    window._selectedElement = null;
    window._elementLocked = false;
    window._currentHighlightedElement = null;
    window._lockedElement = null; // Store golden ("primary") element
    window._secondaryActualElement = []
    window._secondaryElements = []; // To save green ("secondary") elements

    // Remove previous listeners if they exist to prevent duplicates
    if (window._annotationMouseoverListener) {
        window.removeEventListener('mouseover', window._annotationMouseoverListener);
    }
    if (window._annotationMouseoutListener) {
        window.removeEventListener('mouseout', window._annotationMouseoutListener);
    }
    if (window._annotationClickListener) {
        window.removeEventListener('click', window._annotationClickListener, true);
    }
    if (window._annotationKeydownListener) {
        window.removeEventListener('keydown', window._annotationKeydownListener, true);
    }
    if (window._annotationSelectListener) {
        window.removeEventListener('mousedown', window._annotationSelectListener, true);
    }
    if (window._annotationChangeListener) {
        window.removeEventListener('change', window._annotationChangeListener, true);
    }

    // Hover handler
    window._annotationMouseoverListener = (event) => {
        if (!window._annotationMode) return;
        const element = event.target;
        if (element.classList.contains('annotation-primary') || element.classList.contains('annotation-secondary')) return; // Skip locked elements

        // Remove highlight from previous element if exists
        if (window._currentHighlightedElement && window._currentHighlightedElement !== element) {
            window._currentHighlightedElement.classList.remove('annotation-highlight');
        }

        // Highlight current element
        element.classList.add('annotation-highlight');
        window._currentHighlightedElement = element;
    };
    window.addEventListener('mouseover', window._annotationMouseoverListener);

    // Mouse out handler
    window._annotationMouseoutListener = (event) => {
        const element = event.target;
        if (element === window._currentHighlightedElement) {
            element.classList.remove('annotation-highlight');
            window._currentHighlightedElement = null;
        }
    };
    window.addEventListener('mouseout', window._annotationMouseoutListener);

    // Click handler
    window._annotationClickListener = (event) => {
        if (!window._annotationMode) return;

        // Prevent default behavior during annotation mode
        event.preventDefault();
        event.stopImmediatePropagation(); // More forceful than stopPropagation

        const element = event.target;

        // Primary (gold) selection triggered first
        if (!window._elementLocked) {
            window._elementLocked = true;
            element.classList.remove('annotation-highlight'); // Remove blue highlight
            element.classList.add('annotation-primary'); // Add golden highlight

            // Store data for the selected element
            window._selectedElement = {
                tagName: element.tagName,
                id: element.id,
                className: element.className,
                textContent: element.textContent?.trim().substring(0, 100),
                value: element.value, // Capture input value
                xpath: getXPath(element),
                attributes: getAttributes(element)
            };

            // Store reference to locked element
            window._lockedElement = element;

            console.log('Selected primary element (golden):', JSON.stringify(window._selectedElement));
            fetch('http://127.0.0.1:8080/api/notify-primary-selected', {mode: 'no-cors' });
        } else {
            // Secondary (green) element clicked
            if (!element.classList.contains('annotation-secondary') && element !== window._lockedElement) {
                element.classList.remove('annotation-highlight');
                element.classList.add('annotation-secondary'); // Add green highlight

                // Store data for the secondary element
                const secondaryElementData = {
                    tagName: element.tagName,
                    id: element.id,
                    className: element.className,
                    textContent: element.textContent?.trim().substring(0, 100),
                    value: element.value, // Capture input value
                    xpath: getXPath(element),
                    attributes: getAttributes(element)
                };

                window._secondaryElements.push(secondaryElementData);
                window._secondaryActualElement.push(element);
                console.log('Selected secondary element (green):', JSON.stringify(secondaryElementData));
                fetch('http://127.0.0.1:8080/api/notify-secondary-selected', {mode: 'no-cors' });
            }
        }
    };
    window.addEventListener('click', window._annotationClickListener, true);

    // Add these new event listeners to prevent select dropdown and input typing
    window._annotationKeydownListener = (event) => {
        if (window._annotationMode) {
            // Prevent typing in input fields
            if (event.target.tagName === 'INPUT' || event.target.tagName === 'TEXTAREA' || event.target.isContentEditable) {
                event.preventDefault();
                event.stopImmediatePropagation();
            }
        }
    };

    window._annotationSelectListener = (event) => {
        if (window._annotationMode) {
            // Prevent select elements from opening
            if (event.target.tagName === 'SELECT') {
                event.preventDefault();
                event.stopImmediatePropagation();
            }
        }
    };

    // Prevent change events on form elements
    window._annotationChangeListener = (event) => {
        if (window._annotationMode) {
            event.preventDefault();
            event.stopImmediatePropagation();
        }
    };

    window.addEventListener('keydown', window._annotationKeydownListener, true);
    window.addEventListener('mousedown', window._annotationSelectListener, true);
    window.addEventListener('change', window._annotationChangeListener, true);

    // Function to unlock primary element
    window.unlockElement = () => {
        // Remove golden highlight from the primary element
        if (window._lockedElement) {
            window._lockedElement.classList.remove('annotation-primary');
            window._lockedElement = null;
        }
        window._elementLocked = false;
        window._selectedElement = null; // Clear data when unlocking

    // Remove green highlights from all secondary elements
        if (window._secondaryActualElement && window._secondaryActualElement.length > 0) {
            window._secondaryActualElement.forEach((element) => {
                element.classList.remove('annotation-secondary');
            });
            window._secondaryElements = []; // Clear secondary elements array
            window._secondaryActualElement = [];
        }

        console.log('All elements unlocked');
        return true;
    };


    // Function to enable/disable annotation mode
    window.setAnnotationMode = (enabled) => {
        window._annotationMode = !!enabled; // Ensure boolean
        console.log('Annotation mode set to:', window._annotationMode);

        // Set cursor style on document body when in annotation mode
        if (window._annotationMode) {
            document.body.style.cursor = 'crosshair';
        } else {
            document.body.style.cursor = '';
            window.unlockElement(); // Ensure unlocking primary element when disabling
            window._secondaryElements = []; // Clear secondary elements
        }
    };

    // Helper functions
    function getXPath(element) {
        if (element.id !== '')
            return `//*[@id="${element.id}"]`;
        if (element === document.body)
            return '/html/body';

        let ix = 0;
        const siblings = element.parentNode.childNodes;
        for (let i = 0; i < siblings.length; i++) {
            const sibling = siblings[i];
            if (sibling === element)
                return getXPath(element.parentNode) + '/' + element.tagName.toLowerCase() + '[' + (ix + 1) + ']';
            if (sibling.nodeType === 1 && sibling.tagName === element.tagName)
                ix++;
        }
        return null; // Should not happen for valid elements
    }

    function getAttributes(element) {
        const result = {};
        for (const attr of element.attributes) {
            result[attr.name] = attr.value;
        }
        return result;
    }

    window._annotationSetupDone = true; // Mark setup as done
    console.log('Annotation script setup complete.');
};
