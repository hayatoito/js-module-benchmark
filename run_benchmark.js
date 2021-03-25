// Usage: node run_benchmark.js --browser ~/chromium/src/out/Release/chrome

const arg = require('arg');
const handler = require('serve-handler');
const http = require('http');
const puppeteer = require('puppeteer-core');

const args = arg({
    // Types
    '--browser': String,   // browser executable path
    '--depth': Number,     // run only testcases with this depth (2-4)
    '--filter': String,    // run only testcases with this name (prefetch-0|webbundle|bundled)
    '--port': Number,      // http server port (default=8000)
    // Aliases
    '-b': '--browser',
    '-d': '--depth',
    '-f': '--filter',
});

if (!args['--browser'])
    throw new Error('missing required argument: --browser');
const launchOptions = {
    executablePath: args['--browser'],
    args: ['--enable-features=SubresourceWebBundles']
};

async function run(name, browser, url) {
    const page = await browser.newPage();
    await page.goto(url, { waitUntil: 'networkidle0' });
    const ele = await page.$("#log");
    const text = await page.evaluate(elm => elm.textContent, ele);
    const m = text.match(/loadModules duration: ([0-9.]+ms)/);
    console.log(name + ': ' + m[1]);
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
    const port = args['--port'] || 8000;
    server.listen(port);

    for (let name of ['prefetch-0', 'webbundle', 'bundled']) {
        if (args['--filter'] && args['--filter'] !== name)
            continue;
        for (let depth = 2; depth <= 4; depth++) {
            if (args['--depth'] && args['--depth'] !== depth)
                continue;
            await run(`${name} depth=${depth}`, browser, `http://localhost:${port}/out_${depth}/${name}.html`);
        }
    }

    browser.close();
    server.close();
}

main();
