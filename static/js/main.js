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
    const progressText = document.getElementById('progressText');
    
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
        dropzone.classList.add('border-blue-400', 'bg-blue-50', 'shadow-lg');
        dropzone.style.borderStyle = 'solid';
    }
    
    function unhighlight() {
        dropzone.classList.remove('border-blue-400', 'bg-blue-50', 'shadow-lg');
        dropzone.style.borderStyle = 'dashed';
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
            previewDiv.className = 'relative aspect-square bg-white rounded-2xl overflow-hidden shadow-sm border border-gray-100 transition-all duration-300 hover:shadow-md hover:scale-105';
            
            const img = document.createElement('img');
            img.src = e.target.result;
            img.className = 'w-full h-full object-cover';
            img.alt = file.name;
            
            // Create a container for the file info
            const infoContainer = document.createElement('div');
            infoContainer.className = 'absolute bottom-0 left-0 right-0 backdrop-blur-sm bg-white/80 py-2 px-3';
            
            // Create file name element
            const nameLabel = document.createElement('div');
            nameLabel.className = 'text-gray-800 text-xs font-medium truncate';
            nameLabel.textContent = file.name.split('.').slice(0, -1).join('.');
            
            // Create file size element
            const sizeLabel = document.createElement('div');
            sizeLabel.className = 'text-gray-500 text-xs';
            sizeLabel.textContent = formatFileSize(file.size);
            
            infoContainer.appendChild(nameLabel);
            infoContainer.appendChild(sizeLabel);
            
            previewDiv.appendChild(img);
            previewDiv.appendChild(infoContainer);
            imagePreviewContainer.appendChild(previewDiv);
        };
        
        reader.readAsDataURL(file);
    }
    
    // Format file size in a human-readable format
    function formatFileSize(bytes) {
        if (bytes < 1024) return bytes + ' B';
        else if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB';
        else return (bytes / 1048576).toFixed(1) + ' MB';
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
        const progressMessages = [
            "Starting analysis...",
            "Processing images...",
            "Identifying product features...",
            "Generating product details...",
            "Creating description...",
            "Adding product tags...",
            "Finalizing content..."
        ];
        let messageIndex = 0;
        
        const interval = setInterval(() => {
            progress += Math.random() * 8;
            
            if (progress > 15 && messageIndex < 1) {
                messageIndex = 1;
                progressText.textContent = progressMessages[messageIndex];
            } else if (progress > 30 && messageIndex < 2) {
                messageIndex = 2;
                progressText.textContent = progressMessages[messageIndex];
            } else if (progress > 45 && messageIndex < 3) {
                messageIndex = 3;
                progressText.textContent = progressMessages[messageIndex];
            } else if (progress > 60 && messageIndex < 4) {
                messageIndex = 4;
                progressText.textContent = progressMessages[messageIndex];
            } else if (progress > 75 && messageIndex < 5) {
                messageIndex = 5;
                progressText.textContent = progressMessages[messageIndex];
            } else if (progress > 85 && messageIndex < 6) {
                messageIndex = 6;
                progressText.textContent = progressMessages[messageIndex];
            }
            
            if (progress > 90) {
                progress = 90; // Hold at 90% until complete
                clearInterval(interval);
            }
            
            progressBar.style.width = `${progress}%`;
        }, 800);
    });
});
