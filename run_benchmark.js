// Usage: node run_benchmark.js --browser ~/chromium/src/out/Release/chrome

const arg = require('arg');
const handler = require('serve-handler');
const http = require('http');
const puppeteer = require('puppeteer-core');

const args = arg({
    // Types
    '--browser': String,
    // Aliases
    '-b': '--browser',
});

const launchOptions = {
    executablePath: args['--browser'],
    args: ['--enable-features=SubresourceWebBundles']
};

async function run(browser, url) {
    const page = await browser.newPage();
    await page.goto(url, { waitUntil: 'networkidle0' });
    const ele = await page.$("#log");
    const text = await page.evaluate(elm => elm.textContent, ele);
    const m = text.match(/loadModules duration: ([0-9.]+ms)/);
    console.log(url + ': ' + m[1]);
}

async function main() {
    const browser = await puppeteer.launch(launchOptions);
    const server = http.createServer((request, response) => {
        return handler(request, response, {
            public: '.',
            cleanUrls: false,
            headers: [{
                source: '**/*.wbn',
                headers: [
                    { key: 'Content-Type', value: 'application/webbundle' },
                    { key: 'X-Content-Type-Options', value: 'nosniff' },
                ]
            }]
        });
    });
    server.listen(8000);

    await run(browser, 'http://localhost:8000/out_2/webbundle.html');
    await run(browser, 'http://localhost:8000/out_3/webbundle.html');
    await run(browser, 'http://localhost:8000/out_4/webbundle.html');

    browser.close();
    server.close();
}

main();
