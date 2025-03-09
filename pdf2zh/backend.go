package main

import (
	"bytes"
	"fmt"
	"os/exec"
	"io/ioutil"
	"net/http"
)

func callPythonTranslate(filePath string, args map[string]string) ([]byte, error) {
	// 将参数转换为 JSON 格式（示例）
	argsJson, err := json.Marshal(args)
	if err != nil {
		return nil, err
	}

	// 运行 Python 脚本并传递文件路径和参数
	cmd := exec.Command("python", "pdf2zh.py", filePath, string(argsJson))

	// 获取 Python 脚本的输出
	var out bytes.Buffer
	cmd.Stdout = &out
	err = cmd.Run()
	if err != nil {
		return nil, err
	}

	// 返回 Python 的输出（例如翻译后的文件内容）
	return out.Bytes(), nil
}

func translateHandler(w http.ResponseWriter, r *http.Request) {
	// 假设文件上传为 form-data
	file, _, err := r.FormFile("file")
	if err != nil {
		http.Error(w, "Error reading file", http.StatusBadRequest)
		return
	}
	defer file.Close()

	// 假设其他参数是 form-data
	args := map[string]string{
		"some_key": r.FormValue("some_value"),
		// 这里可以加入其它必要的参数
	}

	// 调用 Python 函数
	translatedBytes, err := callPythonTranslate(file, args)
	if err != nil {
		http.Error(w, fmt.Sprintf("Error calling Python: %v", err), http.StatusInternalServerError)
		return
	}

	// 返回翻译后的 PDF 文件
	w.Header().Set("Content-Type", "application/pdf")
	w.Write(translatedBytes)
}

func main() {
	http.HandleFunc("/translate", translateHandler)

	// 启动 HTTP 服务器
	fmt.Println("Starting server on :8080")
	if err := http.ListenAndServe(":8080", nil); err != nil {
		fmt.Println("Error starting server:", err)
	}
}
