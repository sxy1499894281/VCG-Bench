// 全局变量
let allInstructions = [];
let currentIndex = 0;
let filterMode = 'all'; // 'all', 'manually_modified'
let currentModel = null; // 当前选择的模型（单模型模式）
let selectedModels = []; // 选中的多个模型（多模型筛选模式）
let availableModels = []; // 可用模型列表
let useMultiModelFilter = false; // 是否使用多模型筛选
let pendingModels = []; // 待筛选的模型列表（用户添加但未应用筛选）
let currentModifiedModel = null; // 当前查看的修改后渲染图模型（多模型模式下）
let currentInstruction = null; // 当前指令数据
let editHistory = {}; // 编辑历史缓存

// 初始化
document.addEventListener('DOMContentLoaded', function() {
    init();
});

async function init() {
    try {
        await loadModels();
        await loadInstructions();
        if (allInstructions.length > 0) {
            showCurrentInstruction();
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

// 加载指令列表
async function loadInstructions() {
    try {
        let url = '/api/instructions';
        const params = new URLSearchParams();
        
        // 添加模型参数
        if (useMultiModelFilter && selectedModels.length > 0) {
            params.append('models', selectedModels.join(','));
        } else if (currentModel) {
            params.append('model', currentModel);
        }
        
        if (filterMode === 'manually_modified') {
            params.append('manually_modified', 'true');
        }
        
        if (params.toString()) {
            url += '?' + params.toString();
        }
        
        const response = await fetch(url);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const data = await response.json();
        allInstructions = data.instructions || [];
        currentIndex = 0;
    } catch (error) {
        console.error('加载指令失败:', error);
        throw error;
    }
}

// 显示当前指令
async function showCurrentInstruction() {
    if (allInstructions.length === 0) {
        showEmptyMessage();
        return;
    }
    
    const instruction = allInstructions[currentIndex];
    currentInstruction = instruction;
    
    // 加载详细指令数据
    try {
        let url = `/api/instruction/${encodeURIComponent(instruction.domain)}/${encodeURIComponent(instruction.sample_id)}/${encodeURIComponent(instruction.instruction_id)}`;
        if (currentModel) {
            url += '?model=' + encodeURIComponent(currentModel);
        }
        
        const response = await fetch(url);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const detailData = await response.json();
        
        // 合并详细数据（确保 scores 数据正确合并）
        Object.assign(instruction, detailData);
        
        // 特别处理 scores 数据，确保 xdrfr_results 正确传递
        if (detailData.scores && detailData.scores.xdrfr_results) {
            instruction.scores = detailData.scores;
            console.log('Loaded instruction detail with scores:', {
                xdrfr: instruction.scores.xdrfr,
                xdrfr_results_count: instruction.scores.xdrfr_results ? instruction.scores.xdrfr_results.length : 0,
                first_result: instruction.scores.xdrfr_results ? instruction.scores.xdrfr_results[0] : null
            });
        } else {
            console.warn('No xdrfr_results in detailData.scores:', detailData.scores);
        }
        
        currentInstruction = instruction;
        
        // 显示指令内容
        displayInstruction(instruction);
    } catch (error) {
        console.error('加载指令详情失败:', error);
        // 即使加载详情失败，也显示基本信息
        displayInstruction(instruction);
    }
}

// 显示指令内容
function displayInstruction(instruction) {
    // 显示原始渲染图
    const renderedImg = document.getElementById('rendered-img');
    const renderedPlaceholder = document.getElementById('rendered-placeholder');
    
    renderedImg.classList.remove('loaded');
    renderedPlaceholder.classList.remove('hidden');
    renderedPlaceholder.textContent = '加载中...';
    
    renderedImg.onload = function() {
        renderedImg.classList.add('loaded');
        renderedPlaceholder.classList.add('hidden');
    };
    renderedImg.onerror = function() {
        renderedPlaceholder.textContent = '加载失败';
        renderedPlaceholder.classList.remove('hidden');
    };
    renderedImg.src = `/api/image/rendered/${encodeURIComponent(instruction.rendered_path)}`;
    
    // 显示指令文本
    const instructionText = document.getElementById('instruction-text');
    instructionText.value = instruction.instruction || '';
    
    // 更新指令难度选择器
    const instructionLevelSelect = document.getElementById('instruction-level-select');
    if (instruction.instruction_level) {
        instructionLevelSelect.value = instruction.instruction_level;
    }
    
    // 显示修改后的渲染图
    const modifiedImg = document.getElementById('modified-img');
    const modifiedPlaceholder = document.getElementById('modified-placeholder');
    const modifiedModelSelect = document.getElementById('modified-model-select');
    const modelNameBadge = document.getElementById('current-model-name');
    
    modifiedImg.classList.remove('loaded');
    modifiedPlaceholder.classList.remove('hidden');
    modifiedPlaceholder.textContent = '加载中...';
    
    if (useMultiModelFilter && instruction.all_models_modified_paths && Object.keys(instruction.all_models_modified_paths).length > 0) {
        // 多模型模式
        modelNameBadge.style.display = 'none';
        modifiedModelSelect.style.display = 'inline-block';
        
        modifiedModelSelect.innerHTML = '';
        Object.keys(instruction.all_models_modified_paths).forEach(modelName => {
            const option = document.createElement('option');
            option.value = modelName;
            option.textContent = modelName;
            if (modelName === currentModifiedModel || (!currentModifiedModel && modifiedModelSelect.children.length === 0)) {
                option.selected = true;
                currentModifiedModel = modelName;
            }
            modifiedModelSelect.appendChild(option);
        });
        
        const selectedModel = currentModifiedModel || Object.keys(instruction.all_models_modified_paths)[0];
        const modifiedPath = instruction.all_models_modified_paths[selectedModel];
        if (modifiedPath) {
            modifiedImg.onload = function() {
                modifiedImg.classList.add('loaded');
                modifiedPlaceholder.classList.add('hidden');
            };
            modifiedImg.onerror = function() {
                modifiedPlaceholder.textContent = '加载失败';
                modifiedPlaceholder.classList.remove('hidden');
            };
            modifiedImg.src = `/api/image/modified/${encodeURIComponent(modifiedPath)}`;
        }
    } else {
        // 单模型模式
        modifiedModelSelect.style.display = 'none';
        if (instruction.model_name) {
            modelNameBadge.textContent = instruction.model_name;
            modelNameBadge.style.display = 'inline-block';
        } else {
            modelNameBadge.style.display = 'none';
        }
        
        modifiedImg.onload = function() {
            modifiedImg.classList.add('loaded');
            modifiedPlaceholder.classList.add('hidden');
        };
        modifiedImg.onerror = function() {
            modifiedPlaceholder.textContent = '加载失败';
            modifiedPlaceholder.classList.remove('hidden');
        };
        modifiedImg.src = `/api/image/modified/${encodeURIComponent(instruction.modified_path)}`;
    }
    
    // 显示分数
    updateScoresDisplay(instruction.scores || {});
    
    // 显示XDRFR问题集
    displayXDRFRQuestions(instruction);
    
    // 更新进度信息
    document.getElementById('progress').textContent = `${currentIndex + 1}/${allInstructions.length}`;
    document.getElementById('instruction-id').textContent = instruction.instruction_id;
    
    // 更新页码输入框
    const pageInput = document.getElementById('page-input');
    if (pageInput) {
        pageInput.max = allInstructions.length;
        pageInput.value = currentIndex + 1;
    }
    
    // 更新导航按钮状态
    updateNavigationButtons();
    
    // 隐藏空状态提示
    document.getElementById('empty-message').style.display = 'none';
    document.querySelector('.main-content').style.display = 'block';
}

// 更新分数显示
function updateScoresDisplay(scores) {
    const formatScore = (score) => {
        if (score === null || score === undefined) {
            return '-';
        }
        return typeof score === 'number' ? score.toFixed(3) : score;
    };
    
    document.getElementById('score-xdrfr').textContent = formatScore(scores.xdrfr);
    document.getElementById('score-scs').textContent = formatScore(scores.scs);
}

// 显示XDRFR问题集
function displayXDRFRQuestions(instruction) {
    const container = document.getElementById('xdrfr-questions-container');
    container.innerHTML = '';
    
    // 获取问题列表
    const questions = instruction.decomposed_questions || [];
    const xdrfrResults = instruction.scores?.xdrfr_results || [];
    const manualEdits = instruction.manual_edits || {};
    
    if (questions.length === 0) {
        container.innerHTML = '<div style="text-align: center; color: #6c757d; padding: 20px;">暂无问题数据</div>';
        return;
    }
    
    // 添加调试信息：如果 xdrfrResults 为空，显示提示
    if (xdrfrResults.length === 0) {
        const warningDiv = document.createElement('div');
        warningDiv.style.cssText = 'background-color: #fff3cd; border: 1px solid #ffc107; border-radius: 4px; padding: 12px; margin-bottom: 20px; color: #856404;';
        warningDiv.innerHTML = `
            <strong>⚠️ 提示：</strong>未找到评估结果（xdrfr_results）。这可能是因为：
            <ul style="margin: 8px 0 0 20px; padding-left: 0;">
                <li>评估结果文件不存在或路径不正确</li>
                <li>评估尚未运行或失败</li>
                <li>评估结果文件格式不正确</li>
            </ul>
            <div style="margin-top: 8px; font-size: 12px;">
                您可以手动输入答案，系统会保存您的手动编辑。
            </div>
        `;
        container.appendChild(warningDiv);
    }
    
    // 创建问题-答案映射
    const questionAnswerMap = {};
    xdrfrResults.forEach(result => {
        if (result && result.question) {
            questionAnswerMap[result.question] = result;
        }
    });
    
    // 调试信息：输出到控制台
    console.log('XDRFR Questions Debug:', {
        totalQuestions: questions.length,
        totalResults: xdrfrResults.length,
        questionAnswerMapSize: Object.keys(questionAnswerMap).length,
        questions: questions.slice(0, 3), // 前3个问题作为示例
        results: xdrfrResults.slice(0, 3), // 前3个结果作为示例
        instructionScores: instruction.scores,
        questionAnswerMapKeys: Object.keys(questionAnswerMap).slice(0, 3)
    });
    
    // 详细匹配检查
    if (questions.length > 0 && xdrfrResults.length > 0) {
        console.log('Detailed Matching Check:');
        questions.forEach((q, idx) => {
            const matched = questionAnswerMap[q] !== undefined;
            console.log(`  Question ${idx + 1}: ${matched ? '✓' : '✗'} ${matched ? 'Matched' : 'NOT MATCHED'}`);
            if (!matched) {
                console.log(`    Question text: ${q.substring(0, 80)}...`);
                console.log(`    Available keys in map: ${Object.keys(questionAnswerMap).map(k => k.substring(0, 50)).join(', ')}`);
                // 尝试模糊匹配
                const similar = Object.keys(questionAnswerMap).find(k => 
                    k.substring(0, 50) === q.substring(0, 50) || 
                    q.substring(0, 50) === k.substring(0, 50)
                );
                if (similar) {
                    console.log(`    Found similar key: ${similar.substring(0, 80)}...`);
                }
            }
        });
    }
    
    questions.forEach((question, index) => {
        const questionItem = document.createElement('div');
        questionItem.className = 'xdrfr-question-item';
        
        const result = questionAnswerMap[question] || {};
        const originalAnswer = result.answer || '';
        const isSatisfied = result.is_satisfied !== undefined ? result.is_satisfied : null;
        
        // 检查是否有手动编辑
        const editInfo = manualEdits[question];
        const hasEdit = editInfo && editInfo.latest;
        const currentAnswer = hasEdit ? editInfo.latest.modified_answer : originalAnswer;
        
        // 如果原始答案为空且没有手动编辑，显示占位符提示
        const placeholderText = originalAnswer === '' && !hasEdit 
            ? '（答案未找到，请手动输入）' 
            : '';
        
        questionItem.innerHTML = `
            <div class="question-header">
                <div class="question-text">${index + 1}. ${question}</div>
                ${isSatisfied !== null ? `
                    <span class="question-status ${isSatisfied ? 'satisfied' : 'not-satisfied'}">
                        ${isSatisfied ? '满足' : '不满足'}
                    </span>
                ` : ''}
            </div>
            <div class="question-answer-section">
                <label class="answer-label">答案:</label>
                <textarea class="answer-textarea" data-question="${escapeHtml(question)}" data-original="${escapeHtml(originalAnswer)}" placeholder="${escapeHtml(placeholderText)}">${escapeHtml(currentAnswer)}</textarea>
                ${originalAnswer === '' && !hasEdit ? `
                    <div style="font-size: 12px; color: #856404; margin-top: 4px;">
                        <strong>提示：</strong>此问题的答案未找到，请根据实际情况手动输入答案（Yes 或 No）。
                    </div>
                ` : ''}
                <div class="answer-actions">
                    <button class="btn-copy" data-target="${escapeHtml(question)}">复制</button>
                    <button class="btn-save-edit" data-question="${escapeHtml(question)}" ${currentAnswer === originalAnswer ? 'disabled' : ''}>保存修改</button>
                </div>
                ${hasEdit ? `
                    <div class="edit-history">
                        <div class="edit-history-title">修改历史:</div>
                        ${editInfo.history.map(edit => `
                            <div class="edit-history-item">
                                <div class="edit-history-timestamp">${new Date(edit.timestamp).toLocaleString()}</div>
                                <div class="edit-history-content">
                                    <div class="edit-history-original">原答案: ${escapeHtml(edit.original_answer)}</div>
                                    <div class="edit-history-modified">修改后: ${escapeHtml(edit.modified_answer)}</div>
                                </div>
                            </div>
                        `).join('')}
                    </div>
                ` : ''}
            </div>
        `;
        
        container.appendChild(questionItem);
        
        // 设置事件监听器
        const textarea = questionItem.querySelector('.answer-textarea');
        const saveBtn = questionItem.querySelector('.btn-save-edit');
        const copyBtn = questionItem.querySelector('.btn-copy');
        
        // 监听文本变化
        textarea.addEventListener('input', function() {
            const hasChanges = textarea.value !== originalAnswer;
            textarea.classList.toggle('edited', hasChanges);
            saveBtn.disabled = !hasChanges || textarea.value === currentAnswer;
        });
        
        // 保存修改
        saveBtn.addEventListener('click', async function() {
            await saveManualEdit(instruction, question, originalAnswer, textarea.value);
            saveBtn.disabled = true;
        });
        
        // 复制按钮
        copyBtn.addEventListener('click', function() {
            copyToClipboard(textarea.value);
        });
    });
}

// 保存手动编辑
async function saveManualEdit(instruction, question, originalAnswer, modifiedAnswer) {
    try {
        const response = await fetch('/api/edits', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                domain: instruction.domain,
                sample_id: instruction.sample_id,
                instruction_id: instruction.instruction_id,
                question: question,
                original_answer: originalAnswer,
                modified_answer: modifiedAnswer
            })
        });
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        
        // 更新指令数据
        if (!instruction.manual_edits) {
            instruction.manual_edits = {};
        }
        instruction.manual_edits[question] = data.manual_edits[question];
        
        // 重新显示问题（更新编辑历史）
        displayXDRFRQuestions(instruction);
        
        alert('修改已保存');
    } catch (error) {
        console.error('保存修改失败:', error);
        alert('保存修改失败: ' + error.message);
    }
}

// 复制到剪贴板
function copyToClipboard(text) {
    const textarea = document.createElement('textarea');
    textarea.value = text;
    textarea.style.position = 'fixed';
    textarea.style.opacity = '0';
    document.body.appendChild(textarea);
    textarea.select();
    try {
        document.execCommand('copy');
        alert('已复制到剪贴板');
    } catch (err) {
        console.error('复制失败:', err);
        alert('复制失败');
    }
    document.body.removeChild(textarea);
}

// HTML转义
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// 更新导航按钮状态
function updateNavigationButtons() {
    const prevBtn = document.getElementById('btn-prev');
    const nextBtn = document.getElementById('btn-next');
    
    prevBtn.disabled = currentIndex === 0;
    nextBtn.disabled = currentIndex >= allInstructions.length - 1;
}

// 更新筛选按钮状态
function updateFilterButtons() {
    document.querySelectorAll('.btn-filter').forEach(btn => {
        btn.classList.remove('active');
    });
    
    const activeBtn = document.getElementById(`btn-filter-${filterMode === 'manually_modified' ? 'manually-modified' : 'all'}`);
    if (activeBtn) {
        activeBtn.classList.add('active');
    }
}

// 设置事件监听器
function setupEventListeners() {
    // 导航按钮
    document.getElementById('btn-prev').addEventListener('click', () => {
        if (currentIndex > 0) {
            currentIndex--;
            showCurrentInstruction();
        }
    });
    
    document.getElementById('btn-next').addEventListener('click', () => {
        if (currentIndex < allInstructions.length - 1) {
            currentIndex++;
            showCurrentInstruction();
        }
    });
    
    // 跳转按钮
    document.getElementById('btn-jump').addEventListener('click', () => {
        const pageInput = document.getElementById('page-input');
        const page = parseInt(pageInput.value);
        if (page >= 1 && page <= allInstructions.length) {
            currentIndex = page - 1;
            showCurrentInstruction();
        } else {
            alert(`请输入1到${allInstructions.length}之间的页码`);
        }
    });
    
    // 键盘快捷键
    document.addEventListener('keydown', (e) => {
        if (e.target.tagName === 'TEXTAREA' || e.target.tagName === 'INPUT') {
            return;
        }
        if (e.key === 'ArrowLeft' && currentIndex > 0) {
            currentIndex--;
            showCurrentInstruction();
        } else if (e.key === 'ArrowRight' && currentIndex < allInstructions.length - 1) {
            currentIndex++;
            showCurrentInstruction();
        }
    });
    
    // 模型选择器
    document.getElementById('model-select').addEventListener('change', async (e) => {
        currentModel = e.target.value || null;
        useMultiModelFilter = false;
        selectedModels = [];
        updateSelectedModelsList();
        await loadInstructions();
        if (allInstructions.length > 0) {
            currentIndex = 0;
            showCurrentInstruction();
        } else {
            showEmptyMessage();
        }
    });
    
    // 多模型筛选
    document.getElementById('btn-add-model').addEventListener('click', () => {
        const select = document.getElementById('multi-model-add-select');
        const model = select.value;
        if (model && !pendingModels.includes(model)) {
            pendingModels.push(model);
            updateSelectedModelsList();
            select.value = '';
        }
    });
    
    document.getElementById('btn-apply-multi-filter').addEventListener('click', async () => {
        if (pendingModels.length === 0) {
            alert('请先添加至少一个模型');
            return;
        }
        selectedModels = [...pendingModels];
        useMultiModelFilter = true;
        currentModel = null;
        document.getElementById('model-select').value = '';
        await loadInstructions();
        if (allInstructions.length > 0) {
            currentIndex = 0;
            showCurrentInstruction();
        } else {
            showEmptyMessage();
        }
    });
    
    document.getElementById('btn-clear-models').addEventListener('click', () => {
        pendingModels = [];
        selectedModels = [];
        useMultiModelFilter = false;
        updateSelectedModelsList();
    });
    
    // 筛选按钮
    document.getElementById('btn-filter-all').addEventListener('click', async () => {
        filterMode = 'all';
        updateFilterButtons();
        await loadInstructions();
        if (allInstructions.length > 0) {
            currentIndex = 0;
            showCurrentInstruction();
        } else {
            showEmptyMessage();
        }
    });
    
    document.getElementById('btn-filter-manually-modified').addEventListener('click', async () => {
        filterMode = 'manually_modified';
        updateFilterButtons();
        await loadInstructions();
        if (allInstructions.length > 0) {
            currentIndex = 0;
            showCurrentInstruction();
        } else {
            showEmptyMessage();
        }
    });
    
    // 修改后模型选择器（多模型模式）
    document.getElementById('modified-model-select').addEventListener('change', (e) => {
        currentModifiedModel = e.target.value;
        if (currentInstruction) {
            const modifiedPath = currentInstruction.all_models_modified_paths[currentModifiedModel];
            if (modifiedPath) {
                const modifiedImg = document.getElementById('modified-img');
                const modifiedPlaceholder = document.getElementById('modified-placeholder');
                modifiedImg.classList.remove('loaded');
                modifiedPlaceholder.classList.remove('hidden');
                modifiedPlaceholder.textContent = '加载中...';
                modifiedImg.onload = function() {
                    modifiedImg.classList.add('loaded');
                    modifiedPlaceholder.classList.add('hidden');
                };
                modifiedImg.onerror = function() {
                    modifiedPlaceholder.textContent = '加载失败';
                    modifiedPlaceholder.classList.remove('hidden');
                };
                modifiedImg.src = `/api/image/modified/${encodeURIComponent(modifiedPath)}`;
            }
        }
    });
    
    // 复制按钮（指令文本）
    document.querySelectorAll('.btn-copy[data-target="instruction-text"]').forEach(btn => {
        btn.addEventListener('click', () => {
            const instructionText = document.getElementById('instruction-text');
            copyToClipboard(instructionText.value);
        });
    });
}

// 更新已选模型列表显示
function updateSelectedModelsList() {
    const container = document.getElementById('selected-models-list');
    container.innerHTML = '';
    
    if (pendingModels.length === 0) {
        const msg = document.createElement('div');
        msg.className = 'empty-models-msg';
        msg.textContent = '暂无选中模型';
        container.appendChild(msg);
        return;
    }
    
    pendingModels.forEach(model => {
        const item = document.createElement('div');
        item.className = 'selected-model-item';
        item.innerHTML = `
            <span class="model-item-name">${escapeHtml(model)}</span>
            <button class="btn-remove-model" data-model="${escapeHtml(model)}">×</button>
        `;
        container.appendChild(item);
        
        // 移除按钮
        item.querySelector('.btn-remove-model').addEventListener('click', () => {
            pendingModels = pendingModels.filter(m => m !== model);
            updateSelectedModelsList();
        });
    });
}

// 显示空状态
function showEmptyMessage() {
    document.getElementById('empty-message').style.display = 'block';
    document.querySelector('.main-content').style.display = 'none';
}

