#!/usr/bin/env python3
# -*- coding: utf-8 -*-"

# Copyright 2020 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from optparse import OptionParser
from pathlib import Path
import subprocess
import math
import random
from string import Template
import functools

# =============================================================================

ROOT_AXIOM = "A"

# =============================================================================


class Options(object):
    def __init__(self):
        self.setup_option_parser()
        self.parse_options()
        self.validate_options()

    def setup_option_parser(self):
        self.parser = OptionParser("usage: %prog")
        self.parser.add_option(
            "-o",
            "--out",
            default="out",
            help='Specifies the output directory, default="out"',
        )
        self.parser.add_option(
            "-d",
            "--depth",
            type="int",
            default=4,
            help="Specifies the module tree depth, default=4",
        )
        self.parser.add_option(
            "-b",
            "--branches",
            type="int",
            default=10,
            help="Specifies the module tree width at each level, default=10",
        )
        self.parser.add_option(
            "--rules",
            default=None,
            help="Specifies l_system (for instance 'A:AB,B:BBB') rules to "
            "generate the inclusion. "
            "By default the script auto-generates a balanced tree."
            "The start axiom is always 'A'."
            "The rule expansion happens DEPTH times.",
        )
        self.parser.add_option(
            "--sizes",
            default=None,
            help="Specify a size for each module, for instance 'A:10K,B:1.4M'"
            "This is the generated module payload and does not include "
            "module setup and import code for now.",
        )
        self.parser.add_option(
            "--dynamic-imports",
            default=False,
            action="store_true",
            help="Use dynamic imports everywhere.",
        )

    def parse_options(self):
        (self.options, args) = self.parser.parse_args()

    def validate_options(self):
        if self.options.depth < 0:
            self.parser.error("--depth has to be >= 0")
        if self.options.branches <= 0:
            self.parser.error("--branches has to be >= 1")

        if self.options.rules is None:
            self.options.rules = "A:" + "A" * self.options.branches
        self.parse_rules()

        self.parse_sizes()

    def parse_rules(self):
        rules = dict()
        for rule in self.options.rules.split(","):
            predecessor, successors = rule.split(":")
            if len(predecessor) != 1:
                self.parser.error(
                    f"Invalid rule '{rule}'': only 1 char predecessor allowed"
                )
            if len(successors) == 0:
                self.parser.error(f"Invalid rule '{rule}': successor not specified")
            if predecessor in rules:
                self.parser.error(f"More than one rule for '{predecessor}")
            rules[predecessor] = successors
        if "A" not in rules:
            self.parser.error("Missing rule for initial axiom 'A'")
        print("RULES: ", rules)
        self.options.rules = rules

    def parse_sizes(self):
        input_sizes = self.options.sizes
        sizes = self.options.sizes = dict()
        if input_sizes is None:
            return
        for input in input_sizes.split(","):
            symbol, size_string = input.split(":")
            size_string = size_string.lower()
            if size_string.endswith("k"):
                size = int(size_string[:-1]) * 1024
            elif size_string.endswith("m"):
                size = int(size_string[:-1]) * 1024 * 1024
            else:
                size = int(size_string) * 1024
            if symbol in sizes:
                self.parser.error(f"Duplicate size for {symbol}")
            sizes[symbol] = size
        print("SIZES: ", self.options.sizes)


# =============================================================================


class Module(object):
    def __init__(self, name, parent, depth, index=0, size=0, dynamic_import=False):
        self.children = []
        self.simple_name = name
        self.parent = parent
        self.depth = depth
        self.index = index
        self.size = int(size)
        self.dynamic_import = dynamic_import
        if parent:
            # Create unique name based on full path
            path = self.parent.submodule_path / name
            self.name = str(path).replace("/", "_")
            self.path = self.parent.submodule_path / (self.name + ".mjs")
        else:
            self.name = self.simple_name
            self.path = Path(self.name + ".mjs")
        self.submodule_path = self.path.parent / self.simple_name

    def append(self, module):
        self.children.append(module)

    def has_children(self):
        return len(self.children) > 0

    def expand_recurse(self, symbol, options, accumulator):
        if self.depth == options.depth:
            return
        if symbol not in options.rules:
            return
        expansion = options.rules[symbol]
        index = 0
        for symbol in expansion:
            name = f"{symbol}{index}"
            module = Module(
                name,
                parent=self,
                depth=self.depth + 1,
                index=index,
                size=options.sizes.get(symbol, 0),
                dynamic_import=options.dynamic_imports,
            )
            index += 1
            self.append(module)
            accumulator.append(module)
            module.expand_recurse(symbol, options, accumulator)
        return accumulator

    def export(self, out_dir):
        with (out_dir / self.path).open("w") as f:
            operations = []
            operations = self.write_imports(f)
            if self.dynamic_import:
                f.write(f"export async function f_{self.name}() {{\n")
            else:
                f.write(f"export function f_{self.name}() {{\n")
            f.write("  let a=1;\n")
            if self.size:
                f.write("  if (document.evaluate_all) {\n")
                f.write("    a=helper()\n")
                f.write("  }\n")
            if self.dynamic_import:
                f.write(f"  const results = await Promise.all([\n")
                operations = ",\n    ".join(operations)
                f.write(f"    {operations}\n")
                f.write("  ]);\n")
                f.write("  for (let result of results) a += result;\n")
                f.write("  return a;\n")
            else:
                operations.append("a")
                operations = "+".join(operations)
                f.write(f"  return {operations};\n")
            f.write("}\n")
            if self.size:
                f.write("function helper() {\n")
                f.write("  let a=1;")
                # Use random numbers to increase entropy and lower compression quality.
                # The number of random digits dials in the average compression rate:
                # - 10 digits => ~3x
                # -  3 digits => ~5x
                # -  2 digits => ~7x
                random_digits = 10
                instruction_length = (3 + random_digits + 1) + (3 + random_digits + 2)
                min_range = 10 ** (random_digits - 1)
                max_range = 10**random_digits - 1
                for i in range(
                    math.floor((self.size - len(operations) * 2) / instruction_length)
                ):
                    number = random.randint(min_range, max_range)
                    f.write(f"a+={number};a-={number};\n")
                f.write(";\n")
                f.write("  return a+100;\n")
                f.write("}\n")

        if self.has_children():
            (out_dir / self.submodule_path).mkdir()
            for module in self.children:
                module.export(out_dir)

    def write_imports(self, f):
        if self.dynamic_import:
            return self.create_dynamic_imports()
        else:
            return self.write_static_imports(f)

    def create_dynamic_imports(self):
        return [
            f"import('./{self.simple_name}/{module.name}.mjs').then(m => m.f_{module.name}())"
            for module in self.children
        ]

    def write_static_imports(self, f):
        operations = []
        for module in self.children:
            f.write(
                f"import {{f_{module.name}}} from './{self.simple_name}/{module.name}.mjs'\n"
            )
            operations.append(f"f_{module.name}()")
        return operations


# =============================================================================


def step(comment):
    def step_decorator(func):
        @functools.wraps(func)
        def step_wrapper(*args, **kwargs):
            print(f"::group::{comment}")
            result = func(*args, **kwargs)
            print("::endgroup::")
            return result

        return step_wrapper

    return step_decorator


class Benchmark(object):
    def __init__(self, options):
        self.options = options
        self.create_module_tree()

    @functools.lru_cache(maxsize=10)
    def template(self, name):
        template_path = Path(__file__).parent / "html" / f"{name}.template.html"
        with open(template_path, "r") as template_file:
            return Template(template_file.read())

    def benchmark_template(self):
        return self.template("benchmark")

    @step("Creating module tree")
    def create_module_tree(self):
        self.options.module_tree = []
        self.start_module = Module(
            ROOT_AXIOM,
            parent=None,
            depth=0,
            size=0,
            dynamic_import=self.options.dynamic_imports,
        )
        self.modules = self.start_module.expand_recurse(
            ROOT_AXIOM, self.options, accumulator=[]
        )

    @step("Exporting benchmark")
    def export(self, out_path):
        out_path.mkdir(parents=True, exist_ok=True)
        self.export_modules(out_path)
        if not self.options.dynamic_imports:
            self.build_bundles(out_path)
        self.export_html(out_path)

    @step("Exporting modules")
    def export_modules(self, out_path):
        self.start_module.export(out_path)
        print(f" Created {len(self.modules )} modules")

        # Topologically sort paths
        self.modules.sort(key=lambda m: (len(m.path.parts), m.path.parts))

    @step("Building bundles")
    def build_bundles(self, out_path):
        wbn_path = out_path / "bundled.wbn"
        subprocess.check_call(
            # Use `gen-bundle` since a npm's `wbn` (0.0.6) doesn't support a relative url yet.
            f"gen-bundle --dir='{out_path}' --o='{wbn_path}'",
            # Suppresss stderr because gen-bundle` prints each filename to stderr.
            stderr=subprocess.DEVNULL,
            shell=True,
        )

        module_path = out_path / "A.mjs"
        bundle_path = out_path / "bundled.mjs"
        subprocess.check_call(
            f"npx rollup '{ module_path}' --format=esm --file='{bundle_path}' --name=A",
            shell=True,
        )

    @step("Exporting html")
    def export_html(self, out_path):
        benchmarks = []
        benchmarks.append(self.export_benchmark(out_path, f"unbundled.html"))
        benchmarks.append(
            self.export_benchmark(
                out_path, f"modulepreload.html", prefetch_count=len(self.modules)
            )
        )
        benchmarks.append(
            self.export_benchmark(
                out_path, f"script-preload.html", preload_count=len(self.modules)
            )
        )
        if not self.options.dynamic_imports:
            benchmarks.append(self.export_bundled(out_path))
            benchmarks.append(self.export_bundled_wbn(out_path))
        self.export_index(out_path, benchmarks)

    @step("Exporting bundled")
    def export_bundled(self, out_path):
        path = out_path / "rollup.html"
        with open(path, "w") as f:
            f.write(
                self.benchmark_template().substitute(
                    dict(
                        headers="",
                        info=self.output_info(),
                        scripts="",
                        module="./bundled.mjs",
                    )
                )
            )
        return path

    @step("Exporting bundled with webbundle")
    def export_bundled_wbn(self, out_path):
        path = out_path / "webbundle.html"
        with open(path, "w") as f:
            f.write(
                self.benchmark_template().substitute(
                    dict(
                        headers='  <script type="webbundle"> { "source": "bundled.wbn", "scopes": ["./"] } </script>',
                        info=self.output_info(),
                        scripts="",
                        module="./A.mjs",
                    )
                )
            )
        return path

    def export_benchmark(
        self, out_path, file_name, prefetch_count=0, preload_count=0, wait=0
    ):
        print(f"  {file_name}")
        path = out_path / file_name
        with open(path, "w") as f:
            f.write(
                self.benchmark_template().substitute(
                    dict(
                        headers=self.output_headers(prefetch_count),
                        info=self.output_info(),
                        scripts=self.output_scripts(preload_count),
                        module="./A.mjs",
                    )
                )
            )
        return path

    def output_headers(self, prefetch_count):
        return "\n".join(
            [
                f'  <link rel="modulepreload" href="{module.path}">'
                for module in self.modules[:prefetch_count]
            ]
        )

    def output_info(self):
        return f"""
  <dl>
    <dt>Expansion Rules:</dt>
    <dd>{self.options.rules}</dd>
    <dt>Module Sizes:</dt>
    <dd>{self.options.sizes}</dd>
    <dt>Depth:</dt>
    <dd>{self.options.depth}</dd>
    <dt>Module Count:</dt>
    <dd>{len(self.modules)}</dd>
    <dt>Total Source Size:</dt>
    <dd>{round(sum(map(lambda m: m.size, self.modules))/1024/1024, 2)} MiB</dd>
  </dl>"""

    def output_scripts(self, preload_count):
        return "\n".join(
            [
                f'  <script type="module" src="{module.path}"></script>'
                for module in self.modules[:preload_count]
            ]
        )

    def export_index(self, out_path, benchmarks):
        with open(out_path / "index.html", "w") as f:
            f.write(
                self.template("index").substitute(
                    dict(
                        info=self.output_info(),
                        benchmarks=self.output_benchmark_list(out_path, benchmarks),
                    )
                )
            )

    def output_benchmark_list(self, out_path, benchmarks):
        return "\n".join(
            [
                f'  <li><a href="{path.relative_to(out_path)}">{path.name}</a></li>'
                for path in benchmarks
            ]
        )


# =============================================================================
if __name__ == "__main__":
    options = Options().options
    benchmark = Benchmark(options)
    benchmark.export(Path(options.out))
