// Modules to control application life and create native browser window
const { app, BrowserWindow, Menu, ipcMain } = require('electron');
const { exec } = require('child_process');
const kill = require('tree-kill');
const path = require('path');
const fs = require('fs');
const http = require('http');
const ProgressBar = require('electron-progressbar'); // 引入 progressbar

app.setPath('userData', path.join(__dirname, 'userdata'));
let processInstance;
const configPath = path.join(app.getPath('userData'), 'config.json');

const checkService = (url, retries = 100, interval = 1000) => {
  return new Promise((resolve, reject) => {
    let progress = 0;

    // 创建进度条窗口（确定状态）
    const progressBar = new ProgressBar({
      text: '正在检查服务，请稍候...',
      detail: `正在尝试连接服务...`,
      maxValue: retries, // 设置最大值
      browserWindow: {
        parent: null,
        modal: true,
        width: 500,
        height: 170,
        webPreferences: {
          nodeIntegration: true,
          contextIsolation: false,
        },
      },
    });

    progressBar
      .on('completed', () => {
        console.log('Progress bar completed');
        progressBar.close();
      })
      .on('aborted', () => {
        console.log('Progress bar aborted');
        progressBar.close();
        reject(new Error('Progress bar aborted by user'));
      });

    const attempt = () => {
      http
        .get(url, (res) => {
          if (res.statusCode === 200) {
            progressBar.setCompleted(); // 完成进度条
            resolve();
          } else {
            reject(new Error(`Service returned status code ${res.statusCode}`));
          }
        })
        .on('error', (err) => {
          progress++;
          progressBar.value = progress; // 更新进度条值
          progressBar.detail = `正在重试 (${progress}/${retries})...`;

          if (progress < retries) {
            setTimeout(attempt, interval);
          } else {
            progressBar.close();
            reject(new Error('服务启动超时，请检查配置或网络连接'));
          }
        });
    };

    attempt();
  });
};

// Function to load port from config file
const getPortFromConfig = () => {
  try {
    if (fs.existsSync(configPath)) {
      const config = JSON.parse(fs.readFileSync(configPath, 'utf-8'));
      if (config.gradio_port) {
        return config.gradio_port;
      } else {
        throw new Error('配置文件中缺少 "gradio_port" 配置项');
      }
    } else {
      throw new Error('配置文件不存在');
    }
  } catch (error) {
    console.error(`Failed to load config: ${error.message}`);
    dialog.showErrorBox('配置加载失败', `无法加载配置文件：${error.message}`);
    app.quit();
    return null; // Default port
  }
};

const getpdf2zhpathFromConfig = () => {
  try {
    if (fs.existsSync(configPath)) {
      const config = JSON.parse(fs.readFileSync(configPath, 'utf-8'));
      if (config.pdf2zh_path) {
        return config.pdf2zh_path;
      } else {
        throw new Error('配置文件中缺少 "pdf2zh_path" 配置项');
      }
    } else {
      throw new Error('配置文件不存在');
    }
  } catch (error) {
    console.error(`Failed to load config: ${error.message}`);
    dialog.showErrorBox('配置加载失败', `无法加载配置文件：${error.message}`);
    app.quit();
    return null; // Default port
  }
};

const port = getPortFromConfig();
const pdf2zh_path = getpdf2zhpathFromConfig();
const targetURL = `http://localhost:${port}/`;

const createWindow = () => {
  const mainWindow = new BrowserWindow({
    width: 1280,
    height: 880,
    show: false, // Use 'ready-to-show' event to show window
  });

  Menu.setApplicationMenu(null);

  mainWindow.on('ready-to-show', () => {
    mainWindow.show();
  });

  // 加载指定的网页
  mainWindow.loadURL(targetURL);

  ipcMain.on('window-close', () => {
    if (processInstance && processInstance.pid) {
      kill(processInstance.pid, 'SIGTERM', (err) => {
        if (err) {
          console.error(`Failed to kill process: ${err.message}`);
        } else {
          console.log(`Successfully killed process with PID: ${processInstance.pid}`);
        }
      });
    } else {
      console.warn('No process is running.');
    }
  });

  mainWindow.on('closed', () => {
    ipcMain.removeAllListeners('window-close');
  });
};

app.whenReady().then(() => {
  processInstance = exec(`${pdf2zh_path} -i --electron --serverport=${port}`, (error, stdout, stderr) => {
    if (error) {
      console.error(`Error: ${error.message}`);
      app.quit();
      return;
    }
    console.log(`stdout: ${stdout}`);
  });
  checkService(targetURL)
  .then(() => {
    console.log('Service is ready.');
    createWindow();
  })
  .catch((err) => {
    console.error('Service failed to start:', err);
    dialog.showErrorBox('服务启动失败', `无法启动服务：${err.message}`);
    app.quit();
  });
});

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    createWindow();
  }
});

app.on('window-all-closed', () => {
  if (processInstance && processInstance.pid) {
    kill(processInstance.pid, 'SIGTERM', (err) => {
      if (err) {
        console.error(`Failed to kill process: ${err.message}`);
      } else {
        console.log(`Successfully killed process with PID: ${processInstance.pid}`);
      }
    });
  } else {
    console.warn('No process is running.');
  }
  if (process.platform !== 'darwin') {
    app.quit();
  }
});
