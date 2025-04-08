() => {
  // Ensure this script isn't injected multiple times
  if (window._preventNewTabsSetupDone) return;
  window._preventNewTabsSetupDone = true;

  console.log("[Inject] Modifying links to prevent opening in new tabs");

  // Function to process all links on the page
  const processLinks = () => {
    // Find all links with target="_blank" or rel="noopener" attributes
    const links = document.querySelectorAll('a[target="_blank"], a[rel="noopener"], a[rel="noreferrer"]');

    links.forEach(link => {
      // Store original href
      const originalHref = link.getAttribute('href');

      // Remove attributes that cause new tab/window behavior
      link.removeAttribute('target');
      link.removeAttribute('rel');

      // Optional: Log modified links for debugging
      console.log(`[Inject] Modified link: ${originalHref}`);
    });

    // Add a global event listener to handle any dynamically added links
    document.addEventListener('click', (event) => {
      // Check if the clicked element is a link or has a link parent
      let element = event.target;

      // Traverse up to find if any parent is a link (for cases where images or spans are inside links)
      while (element && element !== document.body) {
        if (element.tagName === 'A') {
          // If it's set to open in a new tab or window
          if (element.getAttribute('target') === '_blank' ||
              element.getAttribute('rel')?.includes('noopener') ||
              element.getAttribute('rel')?.includes('noreferrer')) {

            // Prevent the default behavior
            event.preventDefault();

            // Get the href and navigate in the same tab
            const href = element.getAttribute('href');
            if (href && !href.startsWith('javascript:')) {
              window.location.href = href;
            }
          }
          break;
        }
        element = element.parentElement;
      }
    }, true); // Use capture phase to handle the event before default behavior
  };

  // Run the link processor immediately
  processLinks();

  // Also handle links in dynamically loaded content using a MutationObserver
  const observer = new MutationObserver((mutations) => {
    let shouldProcessLinks = false;

    mutations.forEach(mutation => {
      // Check if nodes were added
      if (mutation.addedNodes.length > 0) {
        // Check if any of the added nodes are links or contain links
        for (const node of mutation.addedNodes) {
          if (node.nodeType === Node.ELEMENT_NODE) {
            if (node.tagName === 'A' || node.querySelector('a')) {
              shouldProcessLinks = true;
              break;
            }
          }
        }
      }
    });

    if (shouldProcessLinks) {
      processLinks();
    }
  });

  // Start observing the document with the configured parameters
  observer.observe(document.body, {
    childList: true,
    subtree: true
  });

  return "New tab prevention script injected successfully";
}

