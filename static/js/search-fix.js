// Fix search input styling across all pages (except catalog)
document.addEventListener('DOMContentLoaded', function() {
    // Skip catalog page modifications to prevent conflicts
    if (window.location.pathname.includes('catalog')) {
        return;
    }
    
    // Fix search inputs that might be affected by Bootstrap styling
    const searchInputs = document.querySelectorAll('input[type="text"][placeholder*="Search"]');
    
    searchInputs.forEach(input => {
        // Apply direct styling to prevent text overlapping with search icon
        input.style.paddingLeft = "45px";
        input.style.textIndent = "0";
    });
    
    // Skip the catalog search input
    const catalogSearchInput = document.getElementById('searchInput');
    if (catalogSearchInput && !window.location.pathname.includes('catalog')) {
        catalogSearchInput.style.paddingLeft = "45px";
        catalogSearchInput.style.textIndent = "0";
    }
});