// Usage: node run_benchmark.js --browser ~/chromium/src/out/Release/chrome

const arg = require('arg');
const fs = require('fs');
const handler = require('serve-handler');
const http = require('http');
const http2 = require('http2');
const puppeteer = require('puppeteer-core');
const readline = require('readline');

const args = arg({
    // Types
    '--browser': String,   // browser executable path
    '--depth': Number,     // run only testcases with this depth (2-4)
    '--filter': String,    // run only testcases with this name (prefetch-0|webbundle|bundled)
    '--port': Number,      // http(s) server port (default=8000)
    '--http2': Boolean,    // use http2 local server
    '--certfile': String,  // certificate file (default="cert.pem")
    '--keyfile': String,   // private key file (default="key.pem")
    // Aliases
    '-b': '--browser',
    '-d': '--depth',
    '-f': '--filter',
});

function launchBrowser() {
    if (!args['--browser']) {
        return null;
    }
    const launchOptions = {
        executablePath: args['--browser'],
        args: ['--enable-features=SubresourceWebBundles']
    };
    if (args['--http2']) {
        launchOptions.ignoreHTTPSErrors = true;
    }
    return puppeteer.launch(launchOptions);
}

function createServer(handler) {
    if (args['--http2']) {
        const options = {
            key: fs.readFileSync(args['--keyfile'] || 'key.pem'),
            cert: fs.readFileSync(args['--certfile'] || 'cert.pem')
        };
        return http2.createSecureServer(options, handler);
    } else {
        return http.createServer(handler);
    }
}

async function run(name, browser, url) {
    const page = await browser.newPage();
    await page.goto(url, { waitUntil: 'networkidle0' });
    const ele = await page.$("#log");
    const results = JSON.parse(await page.evaluate(elm => elm.textContent, ele));
    console.log(name + ': ' + (results.importEnd - results.navigationResponseStart));
}

async function main() {
    const browser = await launchBrowser();
    const server = createServer((request, response) => {
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
    const scheme = args['--http2'] ? 'https' : 'http';
    const port = args['--port'] || 8000;
    server.listen(port);

    if (browser) {
        for (let name of ['prefetch-0', 'webbundle', 'bundled']) {
            if (args['--filter'] && args['--filter'] !== name)
                continue;
            for (let depth = 2; depth <= 4; depth++) {
                if (args['--depth'] && args['--depth'] !== depth)
                    continue;
                await run(`${name} depth=${depth}`, browser, `${scheme}://localhost:${port}/out_${depth}/${name}.html`);
            }
        }
        browser.close();
    } else {
        console.log(`Benchmark server listening on ${scheme}://localhost:${port}/`);
        console.log('Hit enter key to stop.');
        const rl = readline.createInterface({
            input: process.stdin,
            output: process.stdout
        });
        await new Promise((resolve) => rl.on('line', resolve));
        rl.close();
    }

    server.close();
}

main();
