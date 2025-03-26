document.addEventListener('DOMContentLoaded', function() {
    // DOM Elements
    const productForm = document.getElementById('productForm');
    const fileInput = document.getElementById('product_images');
    const dropzone = document.getElementById('dropzone');
    const imagePreviewContainer = document.getElementById('imagePreviewContainer');
    const imageError = document.getElementById('imageError');
    const resetButton = document.getElementById('resetButton');
    const loadingOverlay = document.getElementById('loadingOverlay');
    const progressBar = document.getElementById('progressBar');
    
    // Configuration
    const MAX_FILES = 5;
    const MAX_FILE_SIZE = 5 * 1024 * 1024; // 5MB
    const ALLOWED_TYPES = ['image/jpeg', 'image/jpg', 'image/png', 'image/webp'];
    
    // Drag and drop functionality
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        dropzone.addEventListener(eventName, preventDefaults, false);
    });
    
    function preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }
    
    ['dragenter', 'dragover'].forEach(eventName => {
        dropzone.addEventListener(eventName, highlight, false);
    });
    
    ['dragleave', 'drop'].forEach(eventName => {
        dropzone.addEventListener(eventName, unhighlight, false);
    });
    
    function highlight() {
        dropzone.classList.add('border-blue-500', 'bg-blue-50');
    }
    
    function unhighlight() {
        dropzone.classList.remove('border-blue-500', 'bg-blue-50');
    }
    
    // Handle dropped files
    dropzone.addEventListener('drop', handleDrop, false);
    
    function handleDrop(e) {
        const dt = e.dataTransfer;
        const files = dt.files;
        fileInput.files = files;
        handleFiles(files);
    }
    
    // Handle selected files via input
    fileInput.addEventListener('change', function() {
        handleFiles(this.files);
    });
    
    // Process files
    function handleFiles(files) {
        // Reset error message
        showError('');
        
        // Validate number of files
        if (files.length > MAX_FILES) {
            showError(`You can only upload up to ${MAX_FILES} images`);
            resetFileInput();
            return;
        }
        
        // Validate file types and sizes
        let validFiles = true;
        for (let i = 0; i < files.length; i++) {
            const file = files[i];
            
            // Check file type
            if (!ALLOWED_TYPES.includes(file.type)) {
                showError(`File "${file.name}" is not a supported image type`);
                validFiles = false;
                break;
            }
            
            // Check file size
            if (file.size > MAX_FILE_SIZE) {
                showError(`File "${file.name}" exceeds the 5MB size limit`);
                validFiles = false;
                break;
            }
        }
        
        if (!validFiles) {
            resetFileInput();
            return;
        }
        
        // Clear previous previews
        imagePreviewContainer.innerHTML = '';
        
        // Create previews for valid files
        Array.from(files).forEach(file => {
            createImagePreview(file);
        });
        
        // Show preview container
        imagePreviewContainer.classList.remove('hidden');
    }
    
    // Create image preview
    function createImagePreview(file) {
        const reader = new FileReader();
        
        reader.onload = function(e) {
            const previewDiv = document.createElement('div');
            previewDiv.className = 'relative aspect-square bg-gray-100 rounded-lg overflow-hidden';
            
            const img = document.createElement('img');
            img.src = e.target.result;
            img.className = 'w-full h-full object-contain';
            img.alt = file.name;
            
            const nameLabel = document.createElement('div');
            nameLabel.className = 'absolute bottom-0 left-0 right-0 bg-black bg-opacity-50 text-white text-xs p-1 truncate';
            nameLabel.textContent = file.name;
            
            previewDiv.appendChild(img);
            previewDiv.appendChild(nameLabel);
            imagePreviewContainer.appendChild(previewDiv);
        };
        
        reader.readAsDataURL(file);
    }
    
    // Display error message
    function showError(message) {
        if (message) {
            imageError.textContent = message;
            imageError.classList.remove('hidden');
        } else {
            imageError.textContent = '';
            imageError.classList.add('hidden');
        }
    }
    
    // Reset file input
    function resetFileInput() {
        fileInput.value = '';
        imagePreviewContainer.innerHTML = '';
        imagePreviewContainer.classList.add('hidden');
    }
    
    // Reset button functionality
    resetButton.addEventListener('click', function() {
        resetFileInput();
        productForm.reset();
        showError('');
    });
    
    // Form submission
    productForm.addEventListener('submit', function(e) {
        // Validate form before submission
        const productName = document.getElementById('product_name').value.trim();
        const productCategory = document.getElementById('product_category').value.trim();
        const productPrice = document.getElementById('product_price').value.trim();
        
        if (!productName || !productCategory || !productPrice) {
            e.preventDefault();
            return;
        }
        
        if (!fileInput.files || fileInput.files.length === 0) {
            e.preventDefault();
            showError('Please select at least one image');
            return;
        }
        
        // Show loading overlay
        loadingOverlay.classList.remove('hidden');
        
        // Simulate progress (since we can't track actual API progress)
        let progress = 0;
        const interval = setInterval(() => {
            progress += Math.random() * 10;
            if (progress > 90) {
                progress = 90; // Hold at 90% until complete
                clearInterval(interval);
            }
            progressBar.style.width = `${progress}%`;
        }, 500);
    });
});
