# Contributing to the Project

> [!CAUTION]
>
> 当前本项目维护者正在研究文档自动国际化，故不接受任何与文档国际化/文档翻译相关的 PR！
>
> 请勿提交与文档国际化/文档翻译相关的 PR！

感谢您对本项目的兴趣！在您开始贡献之前，请花一些时间阅读以下指南，确保您的贡献能够顺利被接受。

## 不接受的贡献类型

1. 文档国际化/文档翻译
2. 与基础架构有关的贡献，如 HTTP API 等。
3. 明确标出 No help needed 的 Issue。
4. 其他维护者认为不合适的贡献。

请勿提交与上述类型相关的 PR。

## 提交流程

1. Fork 本仓库并克隆到本地。
2. 创建新分支：`git checkout -b feature/<feature-name>`。
3. 进行开发并确保代码符合要求。
4. 提交代码：
   ```bash
   git add .
   git commit -m "<语义化提交信息>"
   ```
5. 推送到您的仓库：`git push origin feature/<feature-name>`。
6. 在 GitHub 上创建 PR，并填写详细说明。然后请求 [@awwaawwa](https://github.com/awwaawwa) Review.
7. 确保通过所有自动化检查。

> [!TIP]
>
> 您无需等到完全开发完成再创建 PR，可以尽早创建，方便我们查看您的实现并提供建议。
>
> 如果您对源代码或相关事宜有任何疑问，请联系维护者 aw@funstory.ai。
>
> 2.0 版本资源文件与 [BabelDOC](https://github.com/funstory-ai/BabelDOC) 共享，相关资源下载代码在 BabelDOC 中。如果您想要添加新的资源文件，请联系 BabelDOC 维护者 aw@funstory.ai。

## 基本要求

1. **工作流程**
   - 请在 `main` 主分支上创建 fork，并在 fork 的分支上进行开发。
   - 提交 Pull Request (PR) 时，请对提交的内容进行详细说明。
   - 如果 PR 没有通过自动化检查（提示 `checks failed` 和红色叉号标记），请查看相应的 `details` 并修改提交内容，确保新的 PR 可以通过自动化检查。

2. **开发和测试**
   - 使用 `pip install -e .` 命令进行开发和测试。

3. **代码格式化**
   - 配置 `pre-commit` 工具，启用 `black` 和 `flake8` 进行代码格式化。

4. **依赖更新**
   - 如果引入了新的依赖，请及时更新 `pyproject.toml` 文件中的依赖列表。

5. **文档更新**
   - 如果添加了新的命令行选项，请同步更新多语言版本的 `README.md` 文件中的命令行选项列表。

6. **提交信息**
   - 使用 [语义化提交信息](https://www.conventionalcommits.org/zh-hans/v1.0.0/)，例如：`feat(translator): add openai`。

7. **编码风格**
   - 请确保提交的代码符合基本的编码风格规范。
   - 变量命名请使用下划线或驼峰命名法。

8. **文档排版**
   - `README.md` 文件的排版请遵循 [中文文案排版指北](https://github.com/sparanoid/chinese-copywriting-guidelines)。
   - 确保英文和中文文档始终保持最新状态，其它语言文档为可选更新。

## 添加翻译接口

1. 在 `pdf2zh/config/translate_engine_model.py` 文件中添加新的翻译器配置类。
2. 在 `pdf2zh/config/translate_engine_model.py` 文件中添加新的翻译器配置类实例到 `TRANSLATION_ENGINE_SETTING_TYPE` 类型别名中。
3. 在 `pdf2zh/translator/translator_impl` 文件夹中添加新的翻译器实现类。

## 项目结构

- **config 文件夹**: 配置系统。
- **translator 文件夹**: 翻译器相关实现。
- **gui.py**: 提供 GUI 界面。
- **const.py**: 一些常量。
- **main.py**: 提供命令行工具。
- **high_level.py**: 基于 BabelDOC 封装出高级接口。
- **http_api.py**: 提供 HTTP API（未开工）。

## 联系我们

如有任何问题，请通过 Issue 或 Telegram Group 提交反馈。感谢您的贡献！

> [!TIP]
>
> [沉浸式翻译](https://immersivetranslate.com) 为本项目的活跃贡献者赞助月度 Pro 会员兑换码，详情请见：[BabelDOC/PDFMathTranslate 贡献者奖励规则
](https://funstory-ai.github.io/BabelDOC/CONTRIBUTOR_REWARD/)