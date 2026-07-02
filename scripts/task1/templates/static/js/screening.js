// 全局变量
let allSamples = [];
let currentIndex = 0;
let filterMode = 'all'; // 'all', 'unmarked', 'approved', 'rejected'
let currentModel = null; // 当前选择的模型（单模型模式）
let selectedModels = []; // 选中的多个模型（多模型筛选模式）
let availableModels = []; // 可用模型列表
let useMultiModelFilter = false; // 是否使用多模型筛选
let pendingModels = []; // 待筛选的模型列表（用户添加但未应用筛选）
let currentRenderedModel = null; // 当前查看的渲染图模型（多模型模式下）

// 初始化
document.addEventListener('DOMContentLoaded', function() {
    init();
});

async function init() {
    try {
        await loadModels();
        await loadSamples();
        await loadStatistics();
        updateFilterButtons(); // 初始化筛选按钮状态
        if (allSamples.length > 0) {
            showCurrentSample();
        } else {
            showEmptyMessage();
        }
        setupEventListeners();
    } catch (error) {
        console.error('初始化失败:', error);
        alert('初始化失败: ' + error.message);
    }
}

// 加载可用模型列表
async function loadModels() {
    try {
        const response = await fetch('/api/models');
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const data = await response.json();
        availableModels = data.models || [];
        const defaultModel = data.default || (availableModels.length > 0 ? availableModels[0] : null);
        
        // 更新模型选择器
        const modelSelect = document.getElementById('model-select');
        modelSelect.innerHTML = '';
        
        if (availableModels.length === 0) {
            const option = document.createElement('option');
            option.value = '';
            option.textContent = '没有可用模型';
            modelSelect.appendChild(option);
            return;
        }
        
        availableModels.forEach(model => {
            const option = document.createElement('option');
            option.value = model;
            option.textContent = model;
            if (model === defaultModel) {
                option.selected = true;
                currentModel = model;
            }
            modelSelect.appendChild(option);
        });
        
        // 更新多模型添加选择器
        const multiModelAddSelect = document.getElementById('multi-model-add-select');
        if (multiModelAddSelect) {
            multiModelAddSelect.innerHTML = '<option value="">选择模型添加到列表...</option>';
            availableModels.forEach(model => {
                const option = document.createElement('option');
                option.value = model;
                option.textContent = model;
                multiModelAddSelect.appendChild(option);
            });
        }
        
        // 更新已选模型列表显示
        updateSelectedModelsList();
    } catch (error) {
        console.error('加载模型列表失败:', error);
        throw error;
    }
}

// 加载样本列表
async function loadSamples() {
    try {
        let url = '/api/samples';
        const params = new URLSearchParams();
        
        // 添加模型参数
        if (useMultiModelFilter && selectedModels.length > 0) {
            // 多模型筛选模式：使用 models 参数（逗号分隔）
            params.append('models', selectedModels.join(','));
        } else if (currentModel) {
            // 单模型模式：使用 model 参数
            params.append('model', currentModel);
        }
        
        if (filterMode === 'unmarked') {
            params.append('unmarked', 'true');
        } else if (filterMode === 'approved') {
            params.append('status', 'approved');
        } else if (filterMode === 'rejected') {
            params.append('status', 'rejected');
        }
        // filterMode === 'all' 时不添加参数
        
        if (params.toString()) {
            url += '?' + params.toString();
        }
        
        const response = await fetch(url);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const data = await response.json();
        allSamples = data.samples || [];
        currentIndex = 0;
    } catch (error) {
        console.error('加载样本失败:', error);
        throw error;
    }
}

// 加载统计信息
async function loadStatistics() {
    try {
        let url = '/api/statistics';
        if (currentModel) {
            url += '?model=' + encodeURIComponent(currentModel);
        }
        
        const response = await fetch(url);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const stats = await response.json();
        updateStatisticsDisplay(stats);
    } catch (error) {
        console.error('加载统计信息失败:', error);
    }
}

// 更新统计信息显示
function updateStatisticsDisplay(stats) {
    document.getElementById('stat-approved').textContent = stats.approved || 0;
    document.getElementById('stat-rejected').textContent = stats.rejected || 0;
    document.getElementById('stat-pending').textContent = stats.pending || 0;
    document.getElementById('stat-total').textContent = stats.total || 0;
}

// 显示当前样本
function showCurrentSample() {
    if (allSamples.length === 0) {
        showEmptyMessage();
        return;
    }
    
    const sample = allSamples[currentIndex];
    
    // 显示图片
    const originalImg = document.getElementById('original-img');
    const renderedImg = document.getElementById('rendered-img');
    const originalPlaceholder = document.getElementById('original-placeholder');
    const renderedPlaceholder = document.getElementById('rendered-placeholder');
    
    // 重置图片状态
    originalImg.classList.remove('loaded');
    renderedImg.classList.remove('loaded');
    originalPlaceholder.classList.remove('hidden');
    renderedPlaceholder.classList.remove('hidden');
    renderedPlaceholder.textContent = '加载中...';
    
    // 设置渲染图的加载事件处理器（必须在设置src之前）
    renderedImg.onload = function() {
        renderedImg.classList.add('loaded');
        renderedPlaceholder.classList.add('hidden');
    };
    renderedImg.onerror = function() {
        renderedPlaceholder.textContent = '加载失败';
        renderedPlaceholder.classList.remove('hidden');
    };
    
    // 加载原图
    originalImg.onload = function() {
        originalImg.classList.add('loaded');
        originalPlaceholder.classList.add('hidden');
    };
    originalImg.onerror = function() {
        originalPlaceholder.textContent = '加载失败';
    };
    originalImg.src = `/api/image/original/${encodeURIComponent(sample.original_path)}`;
    
    // 更新状态按钮高亮
    updateStatusButtons(sample.status);
    
    // 更新进度信息
    document.getElementById('progress').textContent = `${currentIndex + 1}/${allSamples.length}`;
    document.getElementById('sample-id').textContent = sample.sample_id;
    
    // 更新页码输入框的最大值
    const pageInput = document.getElementById('page-input');
    if (pageInput) {
        pageInput.max = allSamples.length;
        pageInput.value = currentIndex + 1;
    }
    
    // 更新模型名称显示和渲染图选择器
    const modelNameBadge = document.getElementById('current-model-name');
    const renderedModelSelect = document.getElementById('rendered-model-select');
    
    if (useMultiModelFilter && sample.all_models_rendered_paths && Object.keys(sample.all_models_rendered_paths).length > 0) {
        // 多模型模式：显示模型选择器（即使只有一个模型也显示，方便查看）
        modelNameBadge.style.display = 'none';
        renderedModelSelect.style.display = 'inline-block';
        
        // 更新选择器选项
        renderedModelSelect.innerHTML = '';
        Object.keys(sample.all_models_rendered_paths).forEach(modelName => {
            const option = document.createElement('option');
            option.value = modelName;
            option.textContent = modelName;
            if (modelName === currentRenderedModel || (!currentRenderedModel && renderedModelSelect.children.length === 0)) {
                option.selected = true;
                currentRenderedModel = modelName;
            }
            renderedModelSelect.appendChild(option);
        });
        
        // 加载选中的模型渲染图
        const selectedModel = currentRenderedModel || Object.keys(sample.all_models_rendered_paths)[0];
        const renderedPath = sample.all_models_rendered_paths[selectedModel];
        if (renderedPath) {
            // onload 和 onerror 已经在函数开头设置好了
            renderedImg.src = `/api/image/rendered/${encodeURIComponent(renderedPath)}`;
        }
    } else {
        // 单模型模式：显示模型名称徽章
        renderedModelSelect.style.display = 'none';
        if (sample.model_name) {
            modelNameBadge.textContent = sample.model_name;
            modelNameBadge.style.display = 'inline-block';
        } else {
            modelNameBadge.style.display = 'none';
        }
        
        // 加载单模型渲染图
        renderedImg.src = `/api/image/rendered/${encodeURIComponent(sample.rendered_path)}`;
    }
    
    // 更新分数显示
    if (useMultiModelFilter && sample.all_models_scores) {
        updateMultiModelScoresDisplay(sample.all_models_scores);
    } else {
        updateScoresDisplay(sample.scores || {});
    }
    
    // 更新导航按钮状态
    updateNavigationButtons();
    
    // 隐藏空状态提示
    document.getElementById('empty-message').style.display = 'none';
    document.querySelector('.main-content').style.display = 'block';
    
    // 清空分数显示（如果样本没有分数信息）
    if (!sample.scores && (!sample.all_models_scores || Object.keys(sample.all_models_scores).length === 0)) {
        if (useMultiModelFilter) {
            document.getElementById('multi-model-scores').innerHTML = '<div class="no-scores-msg">暂无分数数据</div>';
            document.getElementById('single-model-scores').style.display = 'none';
            document.getElementById('multi-model-scores').style.display = 'block';
        } else {
            updateScoresDisplay({});
        }
    }
}

// 更新分数显示（单模型模式）
function updateScoresDisplay(scores) {
    const formatScore = (score) => {
        if (score === null || score === undefined) {
            return '-';
        }
        return typeof score === 'number' ? score.toFixed(3) : score;
    };
    
    document.getElementById('score-scs').textContent = formatScore(scores.scs);
    document.getElementById('score-codevqa').textContent = formatScore(scores.codevqa);
    document.getElementById('score-siglip').textContent = formatScore(scores.siglip);
    
    // 显示单模型分数，隐藏多模型分数
    document.getElementById('single-model-scores').style.display = 'flex';
    document.getElementById('multi-model-scores').style.display = 'none';
}

// 更新多模型分数显示
function updateMultiModelScoresDisplay(allModelsScores) {
    const formatScore = (score) => {
        if (score === null || score === undefined) {
            return '-';
        }
        return typeof score === 'number' ? score.toFixed(3) : score;
    };
    
    const container = document.getElementById('multi-model-scores');
    container.innerHTML = '';
    
    // 创建表格
    const table = document.createElement('table');
    table.className = 'scores-table';
    
    // 表头
    const thead = document.createElement('thead');
    const headerRow = document.createElement('tr');
    headerRow.innerHTML = '<th>模型</th><th>SCS</th><th>CodeVQA</th><th>SigLIP</th>';
    thead.appendChild(headerRow);
    table.appendChild(thead);
    
    // 表体
    const tbody = document.createElement('tbody');
    for (const [modelName, scores] of Object.entries(allModelsScores)) {
        const row = document.createElement('tr');
        row.innerHTML = `
            <td class="model-name-cell">${modelName}</td>
            <td class="score-cell">${formatScore(scores.scs)}</td>
            <td class="score-cell">${formatScore(scores.codevqa)}</td>
            <td class="score-cell">${formatScore(scores.siglip)}</td>
        `;
        tbody.appendChild(row);
    }
    table.appendChild(tbody);
    container.appendChild(table);
    
    // 显示多模型分数，隐藏单模型分数
    document.getElementById('single-model-scores').style.display = 'none';
    document.getElementById('multi-model-scores').style.display = 'block';
}

// 更新状态按钮高亮
function updateStatusButtons(currentStatus) {
    // 移除所有active类
    document.querySelectorAll('.btn-status').forEach(btn => {
        btn.classList.remove('active');
    });
    
    // 添加当前状态的active类
    const statusMap = {
        'approved': 'btn-approved',
        'rejected': 'btn-rejected',
        'pending': 'btn-pending'
    };
    
    const btnId = statusMap[currentStatus];
    if (btnId) {
        const btn = document.getElementById(btnId);
        if (btn) {
            btn.classList.add('active');
        }
    }
}

// 更新导航按钮状态
function updateNavigationButtons() {
    const btnPrev = document.getElementById('btn-prev');
    const btnNext = document.getElementById('btn-next');
    
    btnPrev.disabled = currentIndex === 0;
    btnNext.disabled = currentIndex >= allSamples.length - 1;
}

// 更新状态
async function updateStatus(newStatus) {
    if (allSamples.length === 0) {
        return;
    }
    
    const sample = allSamples[currentIndex];
    
    try {
        const response = await fetch('/api/status', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                sample_id: sample.sample_id,
                domain: sample.domain,
                model_name: sample.model_name || currentModel || (selectedModels.length > 0 ? selectedModels[0] : null),
                status: newStatus
            })
        });
        
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.error || '更新状态失败');
        }
        
        const result = await response.json();
        if (result.success) {
            // 更新本地状态
            sample.status = newStatus;
            updateStatusButtons(newStatus);
            
            // 显示保存成功提示
            console.log(`状态已保存: ${sample.domain}/${sample.sample_id} -> ${newStatus}`);
            if (result.status_path) {
                console.log(`文件路径: ${result.status_path}`);
            }
            
            // 重新加载统计信息
            await loadStatistics();
            
            // 如果筛选模式需要更新列表
            if (filterMode === 'unmarked' && newStatus !== 'pending') {
                // 未打标模式下，标记后需要更新列表
                await loadSamples();
                if (currentIndex >= allSamples.length) {
                    currentIndex = Math.max(0, allSamples.length - 1);
                }
                if (allSamples.length > 0) {
                    showCurrentSample();
                } else {
                    showEmptyMessage();
                }
            } else if (filterMode === 'approved' && newStatus !== 'approved') {
                // 合格模式下，如果标记为非合格，需要更新列表
                await loadSamples();
                if (currentIndex >= allSamples.length) {
                    currentIndex = Math.max(0, allSamples.length - 1);
                }
                if (allSamples.length > 0) {
                    showCurrentSample();
                } else {
                    showEmptyMessage();
                }
            } else if (filterMode === 'rejected' && newStatus !== 'rejected') {
                // 不合格模式下，如果标记为非不合格，需要更新列表
                await loadSamples();
                if (currentIndex >= allSamples.length) {
                    currentIndex = Math.max(0, allSamples.length - 1);
                }
                if (allSamples.length > 0) {
                    showCurrentSample();
                } else {
                    showEmptyMessage();
                }
            }
        } else {
            throw new Error(result.error || '更新失败');
        }
    } catch (error) {
        console.error('更新状态失败:', error);
        alert('更新状态失败: ' + error.message);
    }
}

// 显示空状态
function showEmptyMessage() {
    document.getElementById('empty-message').style.display = 'block';
    document.querySelector('.main-content').style.display = 'none';
    // 清空分数显示
    document.getElementById('single-model-scores').style.display = 'flex';
    document.getElementById('multi-model-scores').style.display = 'none';
    updateScoresDisplay({});
}

// 导航到上一张
function previousSample() {
    if (currentIndex > 0) {
        currentIndex--;
        showCurrentSample();
    }
}

// 导航到下一张
function nextSample() {
    if (currentIndex < allSamples.length - 1) {
        currentIndex++;
        showCurrentSample();
    }
}

// 跳转到指定页码
function jumpToPage(pageNumber) {
    const page = parseInt(pageNumber);
    if (isNaN(page) || page < 1 || page > allSamples.length) {
        alert(`请输入有效的页码 (1-${allSamples.length})`);
        return;
    }
    
    currentIndex = page - 1; // 转换为0-based索引
    showCurrentSample();
}

// 切换筛选模式
async function setFilterMode(mode) {
    if (mode === filterMode) {
        return; // 已经是当前模式，不需要切换
    }
    
    filterMode = mode;
    try {
        await loadSamples();
        currentIndex = 0;
        if (allSamples.length > 0) {
            showCurrentSample();
        } else {
            showEmptyMessage();
        }
        updateFilterButtons();
    } catch (error) {
        console.error('切换筛选模式失败:', error);
        alert('切换筛选模式失败: ' + error.message);
    }
}

// 更新筛选按钮显示
function updateFilterButtons() {
    // 移除所有按钮的 active 类
    document.querySelectorAll('.btn-filter').forEach(btn => {
        btn.classList.remove('active');
    });
    
    // 根据当前模式添加 active 类
    const btnMap = {
        'all': 'btn-filter-all',
        'unmarked': 'btn-filter-unmarked',
        'approved': 'btn-filter-approved',
        'rejected': 'btn-filter-rejected'
    };
    
    const activeBtnId = btnMap[filterMode];
    if (activeBtnId) {
        const btn = document.getElementById(activeBtnId);
        if (btn) {
            btn.classList.add('active');
        }
    }
}

// 切换模型（单模型模式）
async function changeModel(newModel) {
    if (newModel === currentModel && !useMultiModelFilter) {
        return; // 已经是当前模型，不需要切换
    }
    
    // 切换到单模型模式
    useMultiModelFilter = false;
    currentModel = newModel;
    selectedModels = [];
    currentRenderedModel = null; // 重置当前渲染图模型
    
    // 隐藏渲染图模型选择器
    const renderedModelSelect = document.getElementById('rendered-model-select');
    if (renderedModelSelect) {
        renderedModelSelect.style.display = 'none';
    }
    
    try {
        await loadSamples();
        await loadStatistics();
        currentIndex = 0;
        if (allSamples.length > 0) {
            showCurrentSample();
        } else {
            showEmptyMessage();
        }
    } catch (error) {
        console.error('切换模型失败:', error);
        alert('切换模型失败: ' + error.message);
    }
}

// 添加模型到待筛选列表
function addModelToList() {
    const select = document.getElementById('multi-model-add-select');
    const modelName = select.value;
    
    if (!modelName) {
        alert('请先选择一个模型');
        return;
    }
    
    if (pendingModels.includes(modelName)) {
        alert('该模型已在列表中');
        return;
    }
    
    pendingModels.push(modelName);
    updateSelectedModelsList();
    
    // 重置选择器
    select.value = '';
}

// 从待筛选列表删除模型
function removeModelFromList(modelName) {
    pendingModels = pendingModels.filter(m => m !== modelName);
    updateSelectedModelsList();
}

// 更新已选模型列表显示
function updateSelectedModelsList() {
    const listContainer = document.getElementById('selected-models-list');
    listContainer.innerHTML = '';
    
    if (pendingModels.length === 0) {
        const emptyMsg = document.createElement('div');
        emptyMsg.className = 'empty-models-msg';
        emptyMsg.textContent = '暂无模型，请添加模型后点击"应用筛选"';
        listContainer.appendChild(emptyMsg);
        return;
    }
    
    pendingModels.forEach(modelName => {
        const modelItem = document.createElement('div');
        modelItem.className = 'selected-model-item';
        modelItem.innerHTML = `
            <span class="model-item-name">${modelName}</span>
            <button class="btn-remove-model" data-model="${modelName}" title="删除">×</button>
        `;
        listContainer.appendChild(modelItem);
    });
    
    // 添加删除按钮事件
    listContainer.querySelectorAll('.btn-remove-model').forEach(btn => {
        btn.addEventListener('click', () => {
            const modelName = btn.getAttribute('data-model');
            removeModelFromList(modelName);
        });
    });
}

// 清空模型列表
function clearModelsList() {
    pendingModels = [];
    updateSelectedModelsList();
}

// 应用多模型筛选
async function applyMultiModelFilter() {
    if (pendingModels.length === 0) {
        alert('请先添加至少一个模型到列表');
        return;
    }
    
    // 启用多模型筛选模式
    useMultiModelFilter = true;
    selectedModels = [...pendingModels];
    currentModel = null; // 清空单模型选择
    currentRenderedModel = null; // 重置当前渲染图模型
    
    // 清空单模型选择器的选中状态
    const modelSelect = document.getElementById('model-select');
    if (modelSelect) {
        modelSelect.value = '';
    }
    
    try {
        await loadSamples();
        await loadStatistics();
        currentIndex = 0;
        if (allSamples.length > 0) {
            showCurrentSample();
        } else {
            showEmptyMessage();
        }
    } catch (error) {
        console.error('应用多模型筛选失败:', error);
        alert('应用多模型筛选失败: ' + error.message);
    }
}

// 设置事件监听
function setupEventListeners() {
    // 单模型选择器
    document.getElementById('model-select').addEventListener('change', (e) => {
        const selectedModel = e.target.value || null;
        if (selectedModel) {
            // 切换到单模型模式
            useMultiModelFilter = false;
            pendingModels = [];
            selectedModels = [];
            updateSelectedModelsList();
            changeModel(selectedModel);
        }
    });
    
    // 多模型添加按钮
    document.getElementById('btn-add-model').addEventListener('click', addModelToList);
    
    // 应用筛选按钮
    document.getElementById('btn-apply-multi-filter').addEventListener('click', applyMultiModelFilter);
    
    // 清空列表按钮
    document.getElementById('btn-clear-models').addEventListener('click', clearModelsList);
    
    // 多模型添加选择器回车键支持
    document.getElementById('multi-model-add-select').addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            addModelToList();
        }
    });
    
    // 渲染图模型选择器（多模型模式下切换查看不同模型的渲染图）
    const renderedModelSelect = document.getElementById('rendered-model-select');
    if (renderedModelSelect) {
        renderedModelSelect.addEventListener('change', (e) => {
            if (allSamples.length === 0) {
                return;
            }
            const sample = allSamples[currentIndex];
            if (!sample || !sample.all_models_rendered_paths) {
                return;
            }
            
            const selectedModel = e.target.value;
            currentRenderedModel = selectedModel;
            const renderedPath = sample.all_models_rendered_paths[selectedModel];
            
            if (renderedPath) {
                const renderedImg = document.getElementById('rendered-img');
                const renderedPlaceholder = document.getElementById('rendered-placeholder');
                
                // 重置图片状态
                renderedImg.classList.remove('loaded');
                renderedPlaceholder.classList.remove('hidden');
                renderedPlaceholder.textContent = '加载中...';
                
                // 设置加载事件处理器（必须在设置src之前）
                renderedImg.onload = function() {
                    renderedImg.classList.add('loaded');
                    renderedPlaceholder.classList.add('hidden');
                };
                renderedImg.onerror = function() {
                    renderedPlaceholder.textContent = '加载失败';
                    renderedPlaceholder.classList.remove('hidden');
                };
                
                // 加载新渲染图
                renderedImg.src = `/api/image/rendered/${encodeURIComponent(renderedPath)}`;
            }
        });
    }
    
    // 状态按钮
    document.getElementById('btn-approved').addEventListener('click', () => {
        updateStatus('approved');
    });
    document.getElementById('btn-rejected').addEventListener('click', () => {
        updateStatus('rejected');
    });
    document.getElementById('btn-pending').addEventListener('click', () => {
        updateStatus('pending');
    });
    
    // 导航按钮
    document.getElementById('btn-prev').addEventListener('click', previousSample);
    document.getElementById('btn-next').addEventListener('click', nextSample);
    
    // 页码跳转
    document.getElementById('btn-jump').addEventListener('click', () => {
        const pageInput = document.getElementById('page-input');
        jumpToPage(pageInput.value);
    });
    
    // 页码输入框回车键支持
    document.getElementById('page-input').addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            jumpToPage(e.target.value);
        }
    });
    
    // 筛选按钮
    document.getElementById('btn-filter-all').addEventListener('click', () => setFilterMode('all'));
    document.getElementById('btn-filter-unmarked').addEventListener('click', () => setFilterMode('unmarked'));
    document.getElementById('btn-filter-approved').addEventListener('click', () => setFilterMode('approved'));
    document.getElementById('btn-filter-rejected').addEventListener('click', () => setFilterMode('rejected'));
    
    // 键盘快捷键
    document.addEventListener('keydown', (e) => {
        // 忽略在输入框中的按键
        if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') {
            return;
        }
        
        if (e.key === 'ArrowLeft') {
            e.preventDefault();
            previousSample();
        } else if (e.key === 'ArrowRight') {
            e.preventDefault();
            nextSample();
        } else if (e.key === 'a' || e.key === 'A') {
            e.preventDefault();
            updateStatus('approved');
        } else if (e.key === 'r' || e.key === 'R') {
            e.preventDefault();
            updateStatus('rejected');
        } else if (e.key === 'p' || e.key === 'P') {
            e.preventDefault();
            updateStatus('pending');
        }
    });
}

