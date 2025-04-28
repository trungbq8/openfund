// WYSIWYG Editor
const editor = document.getElementById('editor-content');
const previewContainer = document.getElementById('preview-container');
const previewToggle = document.getElementById('toggle-preview');
const imageUploadBtn = document.getElementById('image-upload-btn');
const imageUploadInput = document.getElementById('image-upload');
const imageUploadStatus = document.getElementById('image-upload-status');

editor.addEventListener('focus', function() {
   if (!window.getSelection().toString()) {
      document.execCommand('formatBlock', false, 'p');
   }
});

document.querySelectorAll('.toolbar-btn[data-command]').forEach(button => {
   button.addEventListener('click', function() {
      const command = this.getAttribute('data-command');
      
      if (command === 'h1' || command === 'h2' || command === 'h3' || command === 'p') {
         document.execCommand('formatBlock', false, command);
      } else if (command === 'createLink') {
         const url = prompt('Enter the link URL:', 'https://');
         if (url) document.execCommand(command, false, url);
      } else {
         document.execCommand(command, false, null);
      }
      
      editor.focus();
      updatePreview();
      saveBioContent();
   });
});

previewToggle.addEventListener('click', function() {
   previewContainer.classList.toggle('active');
   if (previewContainer.classList.contains('active')) {
      previewToggle.textContent = 'Close preview';
      previewToggle.classList.add('active');
      updatePreview();
   } else {
      previewToggle.textContent = 'Preview';
      previewToggle.classList.remove('active');
   }
});

function updatePreview() {
   previewContainer.innerHTML = editor.innerHTML;
}

imageUploadBtn.addEventListener('click', function() {
   imageUploadInput.click();
});

imageUploadInput.addEventListener('change', function() {
   if (this.files && this.files[0]) {
      const file = this.files[0];
      uploadImage(file);
      updatePreview();
   }
});

function uploadImage(file) {
   const formData = new FormData();
   formData.append('file', file);
   
   imageUploadStatus.textContent = 'Uploading...';
   
   fetch('/upload-image', {
      method: 'POST',
      body: formData
   })
   .then(response => {
      if (!response.ok) {
         throw new Error('File too large');
      }
      return response.json();
   })
   .then(data => {
      if (data.success) {
         document.execCommand('insertImage', false, data.file_url);
         
         const selection = window.getSelection();
         if (selection.rangeCount > 0) {
            const range = selection.getRangeAt(0);
            const imgNode = range.startContainer.previousSibling;
            
            if (imgNode && imgNode.nodeName === 'IMG') {
               imgNode.style.width = '100%';
               imgNode.style.height = 'auto';
            } 
            else {
               const images = editor.querySelectorAll('img');
               for (let i = images.length - 1; i >= 0; i--) {
                  if (images[i].src === data.file_url) {
                     images[i].style.width = '100%';
                     images[i].style.height = 'auto';
                     break;
                  }
               }
            }
         }
         
         imageUploadStatus.textContent = 'Image uploaded successfully';
      } else {
         throw new Error(data.message || 'Error uploading image');
      }
      
      setTimeout(() => {
         imageUploadStatus.textContent = '';
      }, 3000);
      updatePreview();
      saveBioContent();
   })
   .catch(error => {
      console.error('Error:', error);
      imageUploadStatus.textContent = 'Error uploading image: ' + error.message;
      
      setTimeout(() => {
         imageUploadStatus.textContent = '';
      }, 3000);
      
      updatePreview();
      saveBioContent();
   });
}

editor.addEventListener('input', function() {
   if (!window.getSelection().toString()) {
      document.execCommand('formatBlock', false, 'p');
   }
   updatePreview();
   saveBioContent();
});

function saveBioContent() {
   bioHtmlContent = editor.innerHTML;
   console.log('Bio HTML content saved:', bioHtmlContent);
}