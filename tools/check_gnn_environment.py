#!/usr/bin/env python3
"""
GNN 环境检查脚本
检查 PyTorch、torch_geometric 等依赖是否已安装
"""
import sys
import subprocess

def check_environment():
    """检查 GNN 所需环境"""
    
    print("=" * 80)
    print("🔍 GNN 环境检查")
    print("=" * 80)
    
    results = {
        'python_version': True,
        'torch': False,
        'torch_geometric': False,
        'networkx': False,
        'scipy': False,
        'numpy': False,
        'gpu_available': False
    }
    
    # 1. Python 版本
    print("\n1️⃣ Python 版本检查")
    python_version = sys.version_info
    print(f"   Python {python_version.major}.{python_version.minor}.{python_version.micro}")
    
    if python_version.major >= 3 and python_version.minor >= 8:
        print("   ✅ Python 版本符合要求 (>= 3.8)")
        results['python_version'] = True
    else:
        print("   ⚠️ Python 版本過低，建議 >= 3.8")
        results['python_version'] = False
    
    # 2. PyTorch
    print("\n2️⃣ PyTorch 检查")
    try:
        import torch
        print(f"   ✅ PyTorch 已安装 (版本: {torch.__version__})")
        results['torch'] = True
        
        # 检查 GPU
        if torch.cuda.is_available():
            print(f"   🎮 GPU 可用: {torch.cuda.get_device_name(0)}")
            print(f"   📊 GPU 数量: {torch.cuda.device_count()}")
            results['gpu_available'] = True
        elif hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
            print(f"   🍎 Apple Silicon GPU (MPS) 可用")
            results['gpu_available'] = True
        else:
            print("   💻 仅 CPU 可用（GNN 训练会较慢）")
            results['gpu_available'] = False
    except ImportError:
        print("   ❌ PyTorch 未安装")
        results['torch'] = False
    
    # 3. torch_geometric
    print("\n3️⃣ torch_geometric 检查")
    try:
        import torch_geometric
        print(f"   ✅ torch_geometric 已安装 (版本: {torch_geometric.__version__})")
        results['torch_geometric'] = True
    except ImportError:
        print("   ❌ torch_geometric 未安装")
        results['torch_geometric'] = False
    
    # 4. networkx
    print("\n4️⃣ NetworkX 检查")
    try:
        import networkx as nx
        print(f"   ✅ NetworkX 已安装 (版本: {nx.__version__})")
        results['networkx'] = True
    except ImportError:
        print("   ❌ NetworkX 未安装")
        results['networkx'] = False
    
    # 5. scipy
    print("\n5️⃣ SciPy 检查")
    try:
        import scipy
        print(f"   ✅ SciPy 已安装 (版本: {scipy.__version__})")
        results['scipy'] = True
    except ImportError:
        print("   ❌ SciPy 未安装")
        results['scipy'] = False
    
    # 6. numpy
    print("\n6️⃣ NumPy 检查")
    try:
        import numpy as np
        print(f"   ✅ NumPy 已安装 (版本: {np.__version__})")
        results['numpy'] = True
    except ImportError:
        print("   ❌ NumPy 未安装")
        results['numpy'] = False
    
    # 总结
    print("\n" + "=" * 80)
    print("📊 环境检查总结")
    print("=" * 80)
    
    required = ['python_version', 'torch', 'torch_geometric', 'networkx', 'scipy', 'numpy']
    missing = [k for k in required if not results[k]]
    
    if not missing:
        print("✅ 所有必要依赖已安装，可以开始 GNN 开发！")
        if results['gpu_available']:
            print("🎮 GPU 可用，训练速度会很快")
        else:
            print("💻 仅 CPU 可用，训练会较慢但仍可运行")
        return True
    else:
        print(f"⚠️ 缺少以下依赖: {', '.join(missing)}")
        print("\n安装指令：")
        
        if not results['torch']:
            print("\n# PyTorch (CPU 版本)")
            print("pip3 install torch torchvision torchaudio")
            print("\n# PyTorch (GPU 版本，如果有 NVIDIA GPU)")
            print("pip3 install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118")
        
        if not results['torch_geometric']:
            print("\n# torch_geometric")
            print("pip3 install torch-geometric")
        
        if not results['networkx']:
            print("\n# NetworkX")
            print("pip3 install networkx")
        
        if not results['scipy']:
            print("\n# SciPy")
            print("pip3 install scipy")
        
        if not results['numpy']:
            print("\n# NumPy")
            print("pip3 install numpy")
        
        print("\n或一次性安装所有依赖：")
        print("pip3 install torch torch-geometric networkx scipy numpy")
        
        return False

if __name__ == '__main__':
    success = check_environment()
    
    print("\n" + "=" * 80)
    print("💡 建议")
    print("=" * 80)
    
    if success:
        print("1. 可以立即开始 GNN 实作")
        print("2. 建议先从简单的图构建开始")
        print("3. 预计开发时间：1 周")
    else:
        print("1. 先安装缺少的依赖")
        print("2. 安装完成后重新运行此脚本确认")
        print("3. 如果安装遇到问题，可以选择「简化版」方案（基于图的统计方法）")
