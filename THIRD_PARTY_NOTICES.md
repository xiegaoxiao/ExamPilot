# 第三方组件声明

ExamPilot 自身代码、文档和原创演示材料采用 Apache-2.0；第三方组件继续使用其原有许可证，并不因本项目许可证而重新授权。

源码仓库通过 Python/npm 清单引用依赖，不提交虚拟环境、node_modules 或编译后的前端。构建或再分发包含依赖的应用时，请同时保留相应版权声明、许可文本和上游 NOTICE。[THIRD_PARTY_LICENSES.txt](THIRD_PARTY_LICENSES.txt) 汇集本次锁定的 Python 依赖和 npm 生产依赖随包提供的许可/声明文本；精确版本以锁文件为准，升级依赖后须重新核对。

`vdirs@0.1.8` 的包元数据声明 MIT，但安装包及上游仓库未附完整许可文本；汇总中保留其作者与声明。发布包含该组件的编译包前须向上游核实完整声明。本次仅发布项目源码与依赖清单。

| 主要组件 | 许可 | 上游 |
|---|---|---|
| FastAPI、Pydantic、SQLAlchemy、pytest、AnyIO | MIT | 各 Python 包元数据及随包许可见汇总 |
| Uvicorn、Starlette、HTTPX | BSD-3-Clause | 各 Python 包元数据及随包许可见汇总 |
| python-multipart | Apache-2.0 | 随包许可见汇总 |
| pypdf | BSD-3-Clause | [官方许可](https://github.com/py-pdf/pypdf/blob/main/LICENSE) |
| ReportLab | BSD | [项目](https://www.reportlab.com/)及随包许可见汇总 |
| certifi | MPL-2.0 | [项目](https://github.com/certifi/python-certifi)；仅作为未修改的独立依赖引用 |
| Vue、Vue Router、Pinia、Naive UI、Tailwind CSS、Vite、Vitest | MIT | npm 包元数据；生产依赖文本见汇总，开发工具文本随工具分发 |
| TypeScript | Apache-2.0 | 随包许可见汇总 |
| lucide-vue-next | ISC | [项目许可](https://github.com/lucide-icons/lucide/blob/main/LICENSE) |
| Apache ECharts | Apache-2.0 | [项目许可](https://github.com/apache/echarts/blob/master/LICENSE)及上游 NOTICE 见汇总 |
| Playwright | Apache-2.0 | [项目许可](https://github.com/microsoft/playwright/blob/main/LICENSE)；浏览器另由工具下载，不随本源码仓库分发 |

为了采用 Apache-2.0 开源发布，本版本已将原 Demo 的 PyMuPDF（AGPL/商业双许可）替换为 pypdf；运行和测试清单不再引用 PyMuPDF。旧数据库中的解析器标识及已提取文本保持原样，不发生历史数据迁移或重写。新导入来源记录实际 pypdf 版本。参见 [PyMuPDF 官方许可说明](https://pymupdf.readthedocs.io/en/latest/about.html#license-and-copyright)。

`output/pdf/exampilot-original-demo.pdf` 是本项目生成的原创演示资料。用户自行导入的教材、题目与其他资料不在本项目开源许可授权范围内。
