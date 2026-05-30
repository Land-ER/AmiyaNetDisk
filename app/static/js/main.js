/**
 * AmiyaNetDisk - 前端 JavaScript
 * 功能：密码 SHA-256 哈希、验证码发送
 */

/**
 * 纯 JavaScript SHA-256 哈希（兼容 HTTP 环境，无需 crypto.subtle）
 * 输出 64 位小写十六进制字符串
 * @param {string} str - 输入字符串
 * @returns {string} SHA-256 哈希值
 */
function sha256(str) {
    // 右旋转
    function rotr(n, x) { return (x >>> n) | (x << (32 - n)); }
    // 选择
    function ch(x, y, z) { return (x & y) ^ (~x & z); }
    // 多数
    function maj(x, y, z) { return (x & y) ^ (x & z) ^ (y & z); }
    // Sigma 大写
    function sigma0(x) { return rotr(2, x) ^ rotr(13, x) ^ rotr(22, x); }
    function sigma1(x) { return rotr(6, x) ^ rotr(11, x) ^ rotr(25, x); }
    // Sigma 小写
    function gamma0(x) { return rotr(7, x) ^ rotr(18, x) ^ (x >>> 3); }
    function gamma1(x) { return rotr(17, x) ^ rotr(19, x) ^ (x >>> 10); }

    // 初始哈希值
    var H = [
        0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a,
        0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19
    ];

    // 64 轮常量 K
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
            // 代理对
            i++;
            code = 0x10000 + (((code & 0x3ff) << 10) | (str.charCodeAt(i) & 0x3ff));
            encoded.push(0xf0 | (code >> 18));
            encoded.push(0x80 | ((code >> 12) & 0x3f));
            encoded.push(0x80 | ((code >> 6) & 0x3f));
            encoded.push(0x80 | (code & 0x3f));
        }
    }

    // 填充：附加 0x80，补 0 至长度 ≡ 448 mod 512，附加 64 位长度
    var ml = encoded.length * 8;
    encoded.push(0x80);
    while ((encoded.length * 8) % 512 !== 448) {
        encoded.push(0x00);
    }
    // 追加长度（64 位，大端序）
    for (var i = 0; i < 8; i++) {
        encoded.push((ml >>> (56 - i * 8)) & 0xff);
    }

    // 处理每个 512 位块
    for (var blockStart = 0; blockStart < encoded.length; blockStart += 64) {
        var W = [];
        // 前 16 个字直接取自块数据
        for (var t = 0; t < 16; t++) {
            W[t] = (encoded[blockStart + t * 4] << 24) |
                   (encoded[blockStart + t * 4 + 1] << 16) |
                   (encoded[blockStart + t * 4 + 2] << 8) |
                   (encoded[blockStart + t * 4 + 3]);
        }
        // 扩展到 64 个字
        for (var t = 16; t < 64; t++) {
            W[t] = (gamma1(W[t - 2]) + W[t - 7] + gamma0(W[t - 15]) + W[t - 16]) >>> 0;
        }

        var a = H[0], b = H[1], c = H[2], d = H[3];
        var e = H[4], f = H[5], g = H[6], h = H[7];

        // 64 轮压缩
        for (var t = 0; t < 64; t++) {
            var T1 = (h + sigma1(e) + ch(e, f, g) + K[t] + W[t]) >>> 0;
            var T2 = (sigma0(a) + maj(a, b, c)) >>> 0;
            h = g; g = f; f = e;
            e = (d + T1) >>> 0;
            d = c; c = b; b = a;
            a = (T1 + T2) >>> 0;
        }

        H[0] = (H[0] + a) >>> 0;
        H[1] = (H[1] + b) >>> 0;
        H[2] = (H[2] + c) >>> 0;
        H[3] = (H[3] + d) >>> 0;
        H[4] = (H[4] + e) >>> 0;
        H[5] = (H[5] + f) >>> 0;
        H[6] = (H[6] + g) >>> 0;
        H[7] = (H[7] + h) >>> 0;
    }

    // 输出十六进制字符串
    var hex = '';
    for (var i = 0; i < 8; i++) {
        hex += ('00000000' + H[i].toString(16)).slice(-8);
    }
    return hex;
}

/**
 * 计算密码的 SHA-256 哈希
 * @param {string} password - 原始密码
 * @returns {Promise<string>} 十六进制哈希字符串
 */
async function hashPassword(password) {
    return sha256(password);
}

/**
 * 格式化文件大小
 * @param {number} bytes
 * @returns {string}
 */
function formatFileSize(bytes) {
    const units = ['B', 'KB', 'MB', 'GB', 'TB'];
    let size = bytes;
    for (const unit of units) {
        if (size < 1024) return size.toFixed(1) + ' ' + unit;
        size /= 1024;
    }
    return size.toFixed(1) + ' TB';
}

// 页面加载完成后自动关闭 Flash 消息
document.addEventListener('DOMContentLoaded', function() {
    const flashMessages = document.querySelectorAll('.flash-message');
    flashMessages.forEach(function(msg) {
        setTimeout(function() {
            msg.style.opacity = '0';
            msg.style.transition = 'opacity 0.3s';
            setTimeout(function() {
                msg.remove();
            }, 300);
        }, 5000);
    });
});
