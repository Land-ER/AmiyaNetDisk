/**
 * AmiyaNetDisk - 前端 JavaScript
 * 功能：密码 SHA-256 哈希、验证码发送、Flash 消息自动关闭
 */

/**
 * SHA-256 哈希函数
 * 优先使用 Web Crypto API（HTTPS/Localhost），不支持时回退到纯 JS 实现
 * @param {string} str - 输入字符串
 * @returns {Promise<string>} 64位小写十六进制哈希
 */
async function sha256(str) {
    try {
        var encoder = new TextEncoder();
        var data = encoder.encode(str);
        var hashBuffer = await crypto.subtle.digest('SHA-256', data);
        var hashArray = Array.from(new Uint8Array(hashBuffer));
        return hashArray.map(function(b) { return b.toString(16).padStart(2, '0'); }).join('');
    } catch(e) {
        // crypto.subtle 不可用时回退到纯 JS 实现
        return sha256JS(str);
    }
}
// 模板中调用的是 hashPassword，作为 sha256 的别名
var hashPassword = sha256;

/**
 * 纯 JavaScript SHA-256 实现（兼容 HTTP 环境，无需 crypto.subtle）
 * 参考 FIPS 180-4 标准实现
 * @param {string} str - 输入字符串
 * @returns {string} 64位小写十六进制哈希
 */
function sha256JS(str) {
    function rotr(n, x) { return (x >>> n) | (x << (32 - n)); }
    function ch(x, y, z) { return (x & y) ^ (~x & z); }
    function maj(x, y, z) { return (x & y) ^ (x & z) ^ (y & z); }
    function Sigma0(x) { return rotr(2, x) ^ rotr(13, x) ^ rotr(22, x); }
    function Sigma1(x) { return rotr(6, x) ^ rotr(11, x) ^ rotr(25, x); }
    function gamma0(x) { return rotr(7, x) ^ rotr(18, x) ^ (x >>> 3); }
    function gamma1(x) { return rotr(17, x) ^ rotr(19, x) ^ (x >>> 10); }

    var H = [
        0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a,
        0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19
    ];
    var K = [
        0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5,
        0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
        0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3,
        0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
        0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc,
        0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
        0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7,
        0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
        0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13,
        0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
        0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3,
        0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
        0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5,
        0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
        0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208,
        0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2
    ];

    // UTF-8 编码
    var encoded = [];
    for (var i = 0; i < str.length; i++) {
        var code = str.charCodeAt(i);
        if (code < 0x80) {
            encoded.push(code);
        } else if (code < 0x800) {
            encoded.push(0xc0 | (code >> 6));
            encoded.push(0x80 | (code & 0x3f));
        } else if (code < 0xd800 || code >= 0xe000) {
            encoded.push(0xe0 | (code >> 12));
            encoded.push(0x80 | ((code >> 6) & 0x3f));
            encoded.push(0x80 | (code & 0x3f));
        } else {
            i++;
            code = 0x10000 + (((code & 0x3ff) << 10) | (str.charCodeAt(i) & 0x3ff));
            encoded.push(0xf0 | (code >> 18));
            encoded.push(0x80 | ((code >> 12) & 0x3f));
            encoded.push(0x80 | ((code >> 6) & 0x3f));
            encoded.push(0x80 | (code & 0x3f));
        }
    }

    var ml = encoded.length * 8;
    encoded.push(0x80);
    while ((encoded.length * 8) % 512 !== 448) { encoded.push(0x00); }
    for (var i = 0; i < 8; i++) { encoded.push((ml >>> (56 - i * 8)) & 0xff); }

    for (var blockStart = 0; blockStart < encoded.length; blockStart += 64) {
        var W = [];
        for (var t = 0; t < 16; t++) {
            W[t] = (encoded[blockStart + t * 4] << 24) |
                   (encoded[blockStart + t * 4 + 1] << 16) |
                   (encoded[blockStart + t * 4 + 2] << 8) |
                   (encoded[blockStart + t * 4 + 3]);
        }
        for (var t = 16; t < 64; t++) {
            W[t] = (gamma1(W[t - 2]) + W[t - 7] + gamma0(W[t - 15]) + W[t - 16]) >>> 0;
        }
        var a = H[0], b = H[1], c = H[2], d = H[3];
        var e = H[4], f = H[5], g = H[6], h = H[7];
        for (var t = 0; t < 64; t++) {
            var T1 = (h + Sigma1(e) + ch(e, f, g) + K[t] + W[t]) >>> 0;
            var T2 = (Sigma0(a) + maj(a, b, c)) >>> 0;
            h = g; g = f; f = e; e = (d + T1) >>> 0;
            d = c; c = b; b = a; a = (T1 + T2) >>> 0;
        }
        H[0] = (H[0] + a) >>> 0; H[1] = (H[1] + b) >>> 0;
        H[2] = (H[2] + c) >>> 0; H[3] = (H[3] + d) >>> 0;
        H[4] = (H[4] + e) >>> 0; H[5] = (H[5] + f) >>> 0;
        H[6] = (H[6] + g) >>> 0; H[7] = (H[7] + h) >>> 0;
    }

    function hex(n) {
        var s = '';
        for (var i = 0; i < 4; i++) {
            s += '0123456789abcdef'.charAt((n >>> (24 - i * 8)) >> 4 & 0xf);
            s += '0123456789abcdef'.charAt((n >>> (24 - i * 8)) & 0xf);
        }
        return s;
    }
    return H.map(hex).join('');
}

/**
 * 提交表单时对密码做 SHA-256 哈希，通过隐藏字段提交
 * 密码框内容不被修改——浏览器密码管理器保存的是明文密码
 * @param {HTMLFormElement} form - 表单元素
 * @param {HTMLInputElement} passwordInput - 密码输入框元素
 */
function submitFormWithHashedPassword(form, passwordInput) {
    if (!form || !passwordInput || passwordInput.dataset.hashing === 'true') {
        return;
    }

    passwordInput.dataset.hashing = 'true';

    function submitForm() {
        HTMLFormElement.prototype.submit.call(form);
    }

    function submitWithHash(hash) {
        var fieldName = passwordInput.getAttribute('name');
        if (fieldName) {
            // 创建隐藏字段承载哈希值
            var hidden = document.createElement('input');
            hidden.type = 'hidden';
            hidden.name = fieldName;
            hidden.value = hash;
            form.appendChild(hidden);
            // 密码框移除 name，不提交明文
            passwordInput.removeAttribute('name');
        }
        submitForm();
    }

    hashPassword(passwordInput.value).then(submitWithHash).catch(function() {
        passwordInput.dataset.hashing = 'false';
        alert('密码安全处理失败，请刷新页面后重试。');
    });
}

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
