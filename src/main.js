import { App } from './core/App.js';

document.addEventListener('DOMContentLoaded', async () => {
    window.app = new App();
    
    // 初始化應用程式（包含 IndexedDB）
    await window.app.init();
    
    console.log('✅ App initialized successfully');
});
