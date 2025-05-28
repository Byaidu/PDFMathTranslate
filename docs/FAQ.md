Some questions are frequently asked, so we have provided a list for users who encounter similar issues.  
一些问题经常被问到，所以我们为遇到类似问题的用户提供了一个列表。

## Is a GPU required? / GPU 是必需的吗？
- **Q / 问题**:  
As the program uses artificial intelligence to recognize and extract documents, is GPU required?  
由于程序使用人工智能来识别和提取文件，是否需要 GPU？

- **A / 回答**:  
**GPU is not required.** But if you have a GPU, the program will automatically use it for higher performance.  
**GPU 不是必需的。** 不过，如果您有 GPU，程序将自动使用它以获得更高的性能。

## Downloading interrupted？ / 模型下载中断？
- **Q / 问题**:  
I encountered the following interrupt error while downloading the model. What should I do?  
我在下载模型的时候遇到了如下的中断错误，请问怎么办？

  ![image](https://github.com/user-attachments/assets/3c4eed44-3d9b-4e2f-a224-a58edca718c2)

- **A / 回答**:  
The network is receiving interference, please use a stable network link or try to bypass network intervention.  
网络收到干扰，请使用稳定的网络链接或尝试绕过网络干预。

## How to update to the latest version？/ 怎么更新到最新版本？
- **Q / 问题**:  
I want to use some of the features of the latest version, how do I update it?  
我想用一些最新版本的功能，怎么更新呢？  

- **A / 回答**:  
`pip install -U pdf2zh`


## The following files do not exist: example.pdf / 以下文件不存在：example.pdf
- **Issue / 问题**:  
When executing the program, users would have the following outputs: `The following files do not exist: example.pdf` if the document was not found.  
当执行程序时，如果找不到文档，用户将会看到以下输出：`The following files do not exist: example.pdf`。

- **Solution / 解决方案**:
  - Open the command line in the directory where the file is located, or  
在文件所在目录下打开命令行，或者  
  - Enter the full path of the file directly after pdf2zh, or  
直接在 pdf2zh 后面输入文件完整路径，或者  
  - Use the interactive mode `pdf2zh -i` to drag and drop files directly  
使用交互模式 `pdf2zh -i` 直接拖拽文件。


## SSL Error and Other Network Issues / SSL 错误和其他网络问题
- **Issue / 问题**:  
When downloading hugging face models, users in China may get network error. For example, in [issue #55](https://github.com/Byaidu/PDFMathTranslate/issues/55), [#70](https://github.com/Byaidu/PDFMathTranslate/issues/70).  
在中国下载 Hugging Face 模型时，用户可能会遇到网络错误，例如 [issue #55](https://github.com/Byaidu/PDFMathTranslate/issues/55), [#70](https://github.com/Byaidu/PDFMathTranslate/issues/70)。

- **Solution / 解决方案**:
  - [Bypass GFW / 科学上网](https://github.com/clash-verge-rev/clash-verge-rev).
  - [Use Hugging Face Mirror / 使用 Hugging Face 镜像](https://hf-mirror.com/).
  - [Use Portable version / 使用便携式版本](https://github.com/Byaidu/PDFMathTranslate?tab=readme-ov-file#method-ii-portable).
  - [Use Docker instead / 使用 Docker 替代](https://github.com/Byaidu/PDFMathTranslate#docker).
  - [Update Certificates / 更新证书](https://stackoverflow.com/questions/51925384/unable-to-get-local-issuer-certificate-when-using-requests), as suggested in [issue #55](https://github.com/Byaidu/PDFMathTranslate/issues/55).

## Localhost is not accessible / Localhost 无法访问
同下

## Error launching GUI using 0.0.0.0 / 启动 GUI 出现错误
- **Issue / 问题**:  
Using proxy software in global mode may prevent Gradio from starting properly. For example, in [issue #77](https://github.com/Byaidu/PDFMathTranslate/issues/77).  
使用代理软件的全局模式可能导致 Gradio 无法正常启动，例如 [issue #77](https://github.com/Byaidu/PDFMathTranslate/issues/77)。

- **Solution / 解决方案**:  
Use rule mode / 使用规则模式

  ![image](https://github.com/user-attachments/assets/b1f2b16a-eb6a-4c03-995c-332ef1d82c96)