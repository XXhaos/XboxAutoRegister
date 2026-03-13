const readline = require('readline');

const rl = readline.createInterface({
    input: process.stdin,
    output: process.stdout
});

// 终极破甲器：手动追踪跳转，继承 Cookie，半路截取游戏 ID
async function resolveGameId(startUrl) {
    let currentUrl = startUrl;
    let cookies = {}; 

    for (let i = 0; i < 7; i++) { // 最多追踪 7 层跳转
        try {
            // 拼接继承的 Cookie
            const cookieHeader = Object.entries(cookies).map(([k, v]) => `${k}=${v}`).join('; ');
            
            const response = await fetch(currentUrl, {
                redirect: 'manual', // 关键：关闭自动跳转，改为我们手动一步步跟
                headers: {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.5',
                    'Cookie': cookieHeader
                }
            });

            // 继承服务器发下来的 Cookie，伪装得更像真人
            const setCookieHeader = response.headers.get('set-cookie');
            if (setCookieHeader) {
                const parts = setCookieHeader.split(/,(?=\s*[a-zA-Z0-9_-]+\s*=)/);
                for (const part of parts) {
                    const cookiePair = part.split(';')[0];
                    const [key, ...val] = cookiePair.split('=');
                    if (key && val) cookies[key.trim()] = val.join('=').trim();
                }
            }

            if (response.status >= 300 && response.status < 400) {
                const location = response.headers.get('location');
                if (!location) break;

                const nextUrl = location.startsWith('http') ? location : new URL(location, currentUrl).href;
                
                // 解密 URL，剥开追踪网的层层包装
                let decodedUrl = nextUrl;
                try { decodedUrl = decodeURIComponent(decodedUrl); } catch(e){}
                try { decodedUrl = decodeURIComponent(decodedUrl); } catch(e){}

                // ⭐️ 半路截胡：只要在跳转链接里发现了 9 开头的 12 位代码，直接带走，不再往下跳！
                const idMatch = decodedUrl.match(/(?:\/|id=|ProductId=|bigIds=)([9][A-Za-z0-9]{11})(?:[\/?#&'"]|$)/i);
                if (idMatch) return idMatch[1].toUpperCase();

                currentUrl = nextUrl;
            } else if (response.status === 200) {
                const htmlText = await response.text();

                // 搜刮网页源码，防备 JS 动态跳转
                const htmlMatch = htmlText.match(/(?:\/|id=|ProductId=|bigIds=)([9][A-Za-z0-9]{11})(?:[\/?#&'"]|$)/i);
                if (htmlMatch) return htmlMatch[1].toUpperCase();

                // 检查 Meta Refresh 自动跳转
                const metaRefresh = htmlText.match(/<meta[^>]*http-equiv=["']refresh["'][^>]*content=["']\d+;\s*url=([^"']+)["']/i);
                if (metaRefresh) {
                    currentUrl = metaRefresh[1].replace(/&amp;/g, '&');
                    if (!currentUrl.startsWith('http')) currentUrl = new URL(currentUrl, startUrl).href;
                    continue;
                }

                // 检查 JS 自动跳转
                const jsRedirect = htmlText.match(/(?:window\.)?location(?:\.href)?\s*=\s*['"]([^'"]+)['"]/i);
                if (jsRedirect) {
                    currentUrl = jsRedirect[1];
                    if (!currentUrl.startsWith('http')) currentUrl = new URL(currentUrl, startUrl).href;
                    continue;
                }

                break;
            } else {
                break;
            }
        } catch (e) {
            break;
        }
    }
    return null;
}

// 核心查询逻辑
async function getUSGameData(startUrl) {
    try {
        const urlObj = new URL(startUrl);
        urlObj.searchParams.set('r', 'en-us');
        
        let bigId = await resolveGameId(urlObj.toString());

        if (!bigId) {
            return { success: false, reason: "防爬虫拦截，未能从底层剥离出 12 位游戏代码" };
        }

        const apiUrl = `https://displaycatalog.mp.microsoft.com/v7.0/products?bigIds=${bigId}&market=US&languages=en-us&MS-CV=DUMMY.1`;
        
        const apiResponse = await fetch(apiUrl);
        const data = await apiResponse.json();

        if (!data.Products || data.Products.length === 0) {
            return { success: false, reason: `成功获取 ID (${bigId})，但美区查无此游戏数据` };
        }

        const product = data.Products[0];
        const gameName = product.LocalizedProperties?.[0]?.ProductTitle || "未知游戏";
        
        let finalPrice = null;

        if (!product.DisplaySkuAvailabilities || product.DisplaySkuAvailabilities.length === 0) {
            return { success: false, name: gameName, reason: "该游戏没有销售规格 (无法购买)" };
        }

        // 智能找买断价
        for (const skuObj of product.DisplaySkuAvailabilities) {
            if (skuObj.Sku && (skuObj.Sku.SkuType === 'full' || skuObj.Sku.SkuType === 'dlc' || skuObj.Sku.SkuType === 'consumable')) {
                for (const avail of skuObj.Availabilities || []) {
                    if (avail.Actions && avail.Actions.includes('Purchase') && avail.OrderManagementData?.Price !== undefined) {
                        finalPrice = avail.OrderManagementData.Price.ListPrice;
                        break;
                    }
                }
            }
            if (finalPrice !== null) break;
        }

        if (finalPrice === null) {
            for (const skuObj of product.DisplaySkuAvailabilities) {
                for (const avail of skuObj.Availabilities || []) {
                    if (avail.Actions && avail.Actions.includes('Purchase') && avail.OrderManagementData?.Price !== undefined) {
                        finalPrice = avail.OrderManagementData.Price.ListPrice;
                        break;
                    }
                }
                if (finalPrice !== null) break;
            }
        }

        if (finalPrice === null) {
            return { success: false, name: gameName, reason: "只有 XGP 订阅试玩或捆绑包专属，无单买价格" };
        }

        return { success: true, name: gameName, price: finalPrice };
    } catch (e) {
        return { success: false, reason: `发生异常: ${e.message}` };
    }
}

const inputUrls = [];

console.log('🎮 请粘贴你的 Xbox 链接串 (支持包含回车的多行文本)。');
console.log('💡 提示：粘贴完成后，请在【新的一行】按一次回车开始计算：\n');

rl.on('line', (line) => {
    const trimmedLine = line.trim();
    if (trimmedLine === '') {
        if (inputUrls.length > 0) {
            rl.close();
            processUrls(inputUrls); 
        }
        return;
    }
    const splitUrls = trimmedLine.split(/(?=https?:\/\/)/).filter(u => u.startsWith('http'));
    inputUrls.push(...splitUrls);
});

async function processUrls(urls) {
    console.log(`\n✅ 成功读取到 ${urls.length} 个链接，开始逐个查询美区价格...\n`);
    
    let totalPrice = 0;
    let successCount = 0;
    const failedDetails = [];

    for (let i = 0; i < urls.length; i++) {
        const url = urls[i];
        process.stdout.write(`[${i + 1}/${urls.length}] 正在查询... `);
        
        const result = await getUSGameData(url);
        
        if (result.success) {
            console.log(`✅ 成功 | ${result.name} | 现价: $${result.price}`);
            totalPrice += result.price;
            successCount++;
        } else {
            const namePart = result.name ? `[${result.name}] ` : "";
            console.log(`❌ 失败 | ${namePart}原因: ${result.reason}`);
            failedDetails.push({ url, reason: result.reason, name: result.name });
        }
    }

    console.log("\n================ 结算单 ================");
    console.log(`总计识别: ${urls.length} 个游戏`);
    console.log(`成功查询: ${successCount} 个游戏`);
    console.log(`美元总价: $${totalPrice.toFixed(2)}`);
    console.log("========================================\n");

    if (failedDetails.length > 0) {
        console.log("⚠️ 以下链接需要手动核查：");
        failedDetails.forEach((f, idx) => {
            const nameStr = f.name ? `游戏: ${f.name}\n   ` : "";
            console.log(`${idx + 1}. ${nameStr}原因: ${f.reason}\n   链接: ${f.url}`);
        });
    }
}