// Usage: node run_benchmark.js --browser ~/chromium/src/out/Release/chrome

const commandLineArgs = require('command-line-args');
const localWebServer = require('local-web-server');
const puppeteer = require('puppeteer-core');

const optionDefinitions = [
    { name: 'browser', alias: 'b', type: String },
];
const options = commandLineArgs(optionDefinitions)

const launchOptions = {
    executablePath: options.browser,
};

async function run(browser) {
    const page = await browser.newPage();
    await page.goto('http://localhost:8000/out/bundled.html', { waitUntil: 'networkidle0' });
    const ele = await page.$("#log");
    const text = await page.evaluate(elm => elm.textContent, ele);
    const m = text.match(/loadModules duration: ([0-9.]+ms)/);
    console.log(m[1]);
}

async function main() {
    const browser = await puppeteer.launch(launchOptions);
    const ws = localWebServer.create({
        port: 8000,
        directory: '.'
    });

    await run(browser);

    browser.close();
    ws.server.close();
}

main();
