import os, sys
from typing import List,Dict
import json as Json

def badFunction( x:int,y :str,z)->None:
    a=1
    b= 2
    l = []
    d= {}
    
    if(x==1):
        print ('bad spacing')
    elif(y=="test"):
      print("bad indent")  # 这里用了2个空格而不是4个
    else:
        pass # 无用的 else pass
        
    unused_var = "this is never used"
    
    return None  # 显式返回 None 是不必要的

class badClass:
    def __init__(self):
        self.x = 1
        self._y = 2
        
    def Badly_Named_Method(self):  # 方法名不符合 PEP8
        try:
            result = 1/0
        except:  # 捕获所有异常是不好的做法
            print('error')
        
        return result  # 使用了未定义的变量
    
def unused_function():  # 未使用的函数
    pass

# a中英文混排但是adsfasdf不

# 一行超过88个字符
very_long_variable_name = "this is a very long string that definitely exceeds the recommended line length limit of black and ruff"

# 导入了但未使用的模块
import datetime
import random

x = [1,2,3,]  # 最后多余的逗号
y = [i for i in x]  # 无用的列表推导式 