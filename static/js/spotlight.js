// Mac Spotlight-inspired Search Functionality - Completely rewritten for better reliability
document.addEventListener('DOMContentLoaded', function() {
    // Simple spotlight search implementation
    const searchButtons = document.querySelectorAll('[data-spotlight-trigger]');
    const spotlightModal = document.getElementById('spotlightOverlay');
    const spotlightInput = document.getElementById('spotlightInput');
    const resultsContainer = document.getElementById('spotlightResults');
    const noResultsElement = document.getElementById('noSpotlightResults');
    const loadingElement = document.getElementById('spotlightLoading');
    
    // Add event listeners to all search trigger buttons
    searchButtons.forEach(btn => {
        btn.addEventListener('click', function(e) {
            e.preventDefault();
            openSearch();
        });
    });
    
    // Keyboard shortcuts
    document.addEventListener('keydown', function(e) {
        // Open with Cmd+K or Ctrl+K
        if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
            e.preventDefault();
            openSearch();
        }
        
        // Close with Escape
        if (e.key === 'Escape' && spotlightModal.classList.contains('active')) {
            closeSearch();
        }
    });
    
    // Close when clicking outside
    spotlightModal.addEventListener('click', function(e) {
        if (e.target === spotlightModal) {
            closeSearch();
        }
    });
    
    // Search input handler
    spotlightInput.addEventListener('input', handleSearch);
    
    // Functions
    function openSearch() {
        spotlightModal.style.display = 'flex';
        setTimeout(() => {
            spotlightModal.classList.add('active');
            spotlightInput.focus();
        }, 10);
    }
    
    function closeSearch() {
        spotlightModal.classList.remove('active');
        setTimeout(() => {
            spotlightModal.style.display = 'none';
            resetSearch();
        }, 300);
    }
    
    function resetSearch() {
        spotlightInput.value = '';
        resultsContainer.innerHTML = '';
        noResultsElement.classList.add('hidden');
        loadingElement.classList.add('hidden');
    }
    
    let searchTimeout;
    function handleSearch() {
        const query = spotlightInput.value.trim();
        
        clearTimeout(searchTimeout);
        resultsContainer.innerHTML = '';
        
        if (query.length < 2) {
            noResultsElement.classList.add('hidden');
            loadingElement.classList.add('hidden');
            return;
        }
        
        loadingElement.classList.remove('hidden');
        noResultsElement.classList.add('hidden');
        
        searchTimeout = setTimeout(() => {
            fetchResults(query);
        }, 300);
    }
    
    function fetchResults(query) {
        fetch(`/api/spotlight-search?q=${encodeURIComponent(query)}`)
            .then(response => response.json())
            .then(data => {
                loadingElement.classList.add('hidden');
                resultsContainer.innerHTML = '';
                
                if (data.length === 0) {
                    noResultsElement.classList.remove('hidden');
                    return;
                }
                
                data.forEach(product => {
                    const resultItem = createResultItem(product);
                    resultsContainer.appendChild(resultItem);
                });
            })
            .catch(error => {
                console.error('Search error:', error);
                loadingElement.classList.add('hidden');
                noResultsElement.classList.remove('hidden');
                noResultsElement.innerHTML = '<p>Error searching products</p>';
            });
    }
    
    function createResultItem(product) {
        // Create result item element
        const item = document.createElement('a');
        // item.href = `/view_product/${product.product_id}`;
        item.href = `/product/${product.product_id}`;
        item.className = 'flex items-center p-4 hover:bg-blue-50 transition-colors border-b border-gray-100';
        
        // Icon based on category
        const iconContainer = document.createElement('div');
        iconContainer.className = 'w-10 h-10 flex-shrink-0 rounded-full overflow-hidden bg-blue-50 mr-4 flex items-center justify-center text-blue-600';
        
        let iconClass = 'fas fa-cube';
        if (product.category) {
            const category = product.category.toLowerCase();
            if (category.includes('electronics')) iconClass = 'fas fa-laptop';
            else if (category.includes('fashion')) iconClass = 'fas fa-tshirt';
            else if (category.includes('home')) iconClass = 'fas fa-home';
            else if (category.includes('beauty')) iconClass = 'fas fa-spa';
            else if (category.includes('sports')) iconClass = 'fas fa-football-ball';
            else if (category.includes('toys')) iconClass = 'fas fa-gamepad';
            else if (category.includes('book')) iconClass = 'fas fa-book';
            else if (category.includes('food')) iconClass = 'fas fa-utensils';
        }
        
        iconContainer.innerHTML = `<i class="${iconClass}"></i>`;
        
        // Product info section
        const infoContainer = document.createElement('div');
        infoContainer.className = 'flex-1 min-w-0';
        
        const name = document.createElement('h4');
        name.className = 'text-base font-medium text-gray-900 truncate';
        name.textContent = product.product_name;
        
        const meta = document.createElement('div');
        meta.className = 'flex items-center text-xs text-gray-500 mt-1';
        meta.textContent = product.category;
        
        // Add price if available
        if (product.price && product.price.trim() !== '') {
            const price = document.createElement('span');
            price.className = 'font-medium ml-2 text-gray-600';
            price.textContent = product.price.startsWith('$') ? product.price : `$${product.price}`;
            meta.appendChild(price);
        }
        
        infoContainer.appendChild(name);
        infoContainer.appendChild(meta);
        
        // Product image if available
        if (product.image_urls && product.image_urls.length > 0) {
            const imageContainer = document.createElement('div');
            imageContainer.className = 'w-12 h-12 flex-shrink-0 rounded-md overflow-hidden bg-gray-100 ml-4';
            
            const img = document.createElement('img');
            img.src = product.image_urls[0];
            img.alt = product.product_name;
            img.className = 'w-full h-full object-cover';
            
            imageContainer.appendChild(img);
            item.appendChild(iconContainer);
            item.appendChild(infoContainer);
            item.appendChild(imageContainer);
        } else {
            item.appendChild(iconContainer);
            item.appendChild(infoContainer);
        }
        
        // Arrow icon
        const arrow = document.createElement('div');
        arrow.className = 'ml-2 text-gray-400 flex-shrink-0';
        arrow.innerHTML = '<i class="fas fa-chevron-right text-xs"></i>';
        item.appendChild(arrow);
        
        return item;
    }
});