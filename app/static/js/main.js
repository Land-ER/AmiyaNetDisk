/**
 * AmiyaNetDisk - 前端 JavaScript
 * 功能：密码 SHA-256 哈希、验证码发送、Flash 消息自动关闭
 */

/**
 * SHA-256 哈希函数（使用 Web Crypto API，兼容 HTTPS/Localhost）
 * 不依赖任何外部脚本，纯浏览器原生 API
 * @param {string} str - 输入字符串
 * @returns {Promise<string>} 64位十六进制哈希
 */
async function sha256(str) {
    try {
        var encoder = new TextEncoder();
        var data = encoder.encode(str);
        var hashBuffer = await crypto.subtle.digest('SHA-256', data);
        var hashArray = Array.from(new Uint8Array(hashBuffer));
        return hashArray.map(function(b) { return b.toString(16).padStart(2, '0'); }).join('');
    } catch(e) {
        // crypto.subtle 不可用时直接返回原文
        return str;
    }
}
// 模板中调用的是 hashPassword，作为 sha256 的别名
var hashPassword = sha256;

/**
 * 格式化文件大小
 * @param {number} bytes
 * @returns {string}
 */
function formatFileSize(bytes) {
    var units = ['B', 'KB', 'MB', 'GB', 'TB'];
    var size = bytes;
    for (var i = 0; i < units.length; i++) {
        if (size < 1024) return size.toFixed(1) + ' ' + units[i];
        size /= 1024;
    }
    return size.toFixed(1) + ' TB';
}

// 页面加载完成后自动关闭 Flash 消息
document.addEventListener('DOMContentLoaded', function() {
    var flashMessages = document.querySelectorAll('.flash-message');
    flashMessages.forEach(function(msg) {
        setTimeout(function() {
            msg.style.opacity = '0';
            msg.style.transition = 'opacity 0.3s';
            setTimeout(function() {
                msg.remove();
            }, 300);
        }, 5000);
    });

    // 初始化标签输入组件
    initTagInputs();
});

/**
 * 标签输入组件
 * 将普通文本输入框改为带建议下拉和标签chip的交互组件
 */
function initTagInputs() {
    var wrappers = document.querySelectorAll('.tag-input-wrapper');
    wrappers.forEach(function(wrapper) {
        var input = wrapper.querySelector('.tag-input-field');
        var hidden = wrapper.querySelector('.tag-hidden-input');
        var list = wrapper.querySelector('.tag-list');
        var suggestions = wrapper.querySelector('.tag-suggestions');
        var allTags = [];
        try { allTags = JSON.parse(wrapper.getAttribute('data-all-tags') || '[]'); } catch(e) {}
        var tags = [];

        // 从隐藏输入初始化已有标签
        if (hidden && hidden.value) {
            tags = hidden.value.split(',').map(function(t) { return t.trim(); }).filter(Boolean);
            renderTags();
        }

        // 渲染标签chip
        function renderTags() {
            list.innerHTML = '';
            tags.forEach(function(tag, i) {
                var chip = document.createElement('span');
                chip.className = 'tag-chip';
                chip.innerHTML = tag + '<button type="button" class="tag-chip-remove" data-index="' + i + '">&times;</button>';
                chip.querySelector('.tag-chip-remove').addEventListener('click', function() {
                    tags.splice(i, 1);
                    renderTags();
                    syncHidden();
                    input.focus();
                });
                list.appendChild(chip);
            });
            syncHidden();
        }

        // 同步隐藏输入
        function syncHidden() {
            if (hidden) hidden.value = tags.join(',');
        }

        // 添加标签
        function addTag(text) {
            text = text.trim();
            if (!text || tags.indexOf(text) !== -1) return;
            tags.push(text);
            renderTags();
            input.value = '';
            hideSuggestions();
            input.focus();
        }

        // 显示建议
        function showSuggestions(filter) {
            var filtered = [];
            var lower = filter.toLowerCase();
            allTags.forEach(function(t) {
                if (t.toLowerCase().indexOf(lower) !== -1 && tags.indexOf(t) === -1) {
                    filtered.push(t);
                }
            });
            if (filtered.length === 0 || !filter) {
                hideSuggestions();
                return;
            }
            suggestions.innerHTML = '';
            filtered.forEach(function(t) {
                var item = document.createElement('div');
                item.className = 'tag-suggestion-item';
                var idx = t.toLowerCase().indexOf(lower);
                if (idx !== -1) {
                    item.innerHTML = t.slice(0, idx) + '<span class="highlight">' + t.slice(idx, idx + lower.length) + '</span>' + t.slice(idx + lower.length);
                } else {
                    item.textContent = t;
                }
                item.addEventListener('mousedown', function(e) {
                    e.preventDefault();
                    addTag(t);
                });
                suggestions.appendChild(item);
            });
            suggestions.classList.add('visible');
        }

        function hideSuggestions() {
            suggestions.classList.remove('visible');
        }

        // 输入事件
        input.addEventListener('input', function() {
            showSuggestions(this.value);
        });

        input.addEventListener('keydown', function(e) {
            if (e.key === 'Enter') {
                e.preventDefault();
                var active = suggestions.querySelector('.tag-suggestion-item.active');
                if (active) {
                    addTag(active.textContent);
                } else if (this.value.trim()) {
                    addTag(this.value);
                }
            } else if (e.key === 'Escape') {
                hideSuggestions();
            } else if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
                e.preventDefault();
                var items = suggestions.querySelectorAll('.tag-suggestion-item');
                if (items.length === 0) return;
                var idx = -1;
                items.forEach(function(item, i) {
                    if (item.classList.contains('active')) idx = i;
                    item.classList.remove('active');
                });
                if (e.key === 'ArrowDown') {
                    idx = Math.min(idx + 1, items.length - 1);
                } else {
                    idx = Math.max(idx - 1, 0);
                }
                items[idx].classList.add('active');
                items[idx].scrollIntoView({ block: 'nearest' });
            }
        });

        input.addEventListener('blur', function() {
            setTimeout(hideSuggestions, 150);
        });

        document.addEventListener('click', function(e) {
            if (!wrapper.contains(e.target)) hideSuggestions();
        });
    });
}
