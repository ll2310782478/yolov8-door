// 简单的前端逻辑，用于 NFC 卡片管理与点击触发扫描

const apiBase = '/api/hardware';

async function fetchUsers(){
  // 获取用户列表用于选择
  try{
    const res = await fetch('/api/users');
    const users = await res.json();
    const sel = document.getElementById('userSelect');
    sel.innerHTML = '<option value="">-- 选择用户 --</option>';
    users.forEach(u => {
      const opt = document.createElement('option');
      opt.value = u.id;
      opt.textContent = `${u.id} - ${u.username}`;
      sel.appendChild(opt);
    });
  }catch(e){ console.error('fetchUsers error', e); }
}

async function fetchDevices(){
  const res = await fetch(apiBase + '/devices');
  const data = await res.json();
  const sel = document.getElementById('deviceSelect');
  sel.innerHTML = '';
  if(data.length === 0){
    sel.innerHTML = '<option value="">-- 无可用设备 --</option>';
  } else {
    data.forEach(d => {
      const opt = document.createElement('option');
      opt.value = d.device_id;
      opt.textContent = `${d.device_name || d.device_id} (${d.device_type})`;
      sel.appendChild(opt);
    });
  }
}

async function fetchCards(){
  const res = await fetch(apiBase + '/nfc/cards');
  const cards = await res.json();
  const tbody = document.querySelector('#cardsTable tbody');
  
  if(cards.length === 0){
    tbody.innerHTML = '<tr><td colspan="7" style="text-align:center; color:#718096;">暂无卡片数据</td></tr>';
    return;
  }
  
  tbody.innerHTML = '';
  for(const c of cards){
    const tr = document.createElement('tr');
    const statusBadge = c.is_active ? '<span class="status-badge status-active">启用</span>' : '<span class="status-badge status-inactive">禁用</span>';
    tr.innerHTML = `
      <td>${c.id}</td>
      <td>${c.user_id}</td>
      <td><code style="background:#f7fafc; padding:0.25rem 0.5rem; border-radius:4px;">${c.card_number}</code></td>
      <td>${c.card_name || '-'}</td>
      <td>${statusBadge}</td>
      <td>${c.permission_end_date ? new Date(c.permission_end_date).toLocaleDateString() : '永久'} / ${c.max_daily_uses || '无限'}</td>
      <td style="display:flex; gap:0.5rem;">
        <button class="btn-outline" style="padding:0.4rem 0.8rem; font-size:0.85rem;" onclick="openEditModal(${c.id})">编辑</button>
        <button class="btn-outline" style="padding:0.4rem 0.8rem; font-size:0.85rem; color:#f56565;" onclick="deleteCard(${c.id})">删除</button>
      </td>
    `;
    tbody.appendChild(tr);
  }
}

async function createCard(evt){
  evt.preventDefault();
  const user_id = document.getElementById('userSelect').value;
  if(!user_id){
    showAlert('请选择用户', 'danger');
    return;
  }
  const card_number = document.getElementById('cardNumber').value.trim();
  const card_name = document.getElementById('cardName').value.trim();
  const permissionEnd = document.getElementById('permissionEnd').value;
  const maxDaily = document.getElementById('maxDaily').value || 0;
  
  const payload = {user_id: Number(user_id), card_number: card_number, card_name: card_name, max_daily_uses: Number(maxDaily)};
  if(permissionEnd) payload.permission_end_date = new Date(permissionEnd).toISOString();
  
  const res = await fetch(apiBase + '/nfc/cards', {
    method: 'POST',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify(payload)
  });
  
  if(res.ok){
    showAlert('卡片添加成功', 'success');
    document.getElementById('createForm').reset();
    await fetchCards();
  } else {
    const err = await res.json();
    showAlert('添加失败: ' + (err.detail || '未知错误'), 'danger');
  }
}

async function deleteCard(id){
  if(!confirm('确定删除该卡片？')) return;
  const res = await fetch(apiBase + '/nfc/card/' + id, {method:'DELETE'});
  if(res.ok){
    showAlert('卡片已删除', 'success');
    await fetchCards();
  } else {
    showAlert('删除失败', 'danger');
  }
}

function showAlert(message, type='info', timeout=4000){
  const area = document.getElementById('alertArea');
  const id = 'a' + Date.now();
  const div = document.createElement('div');
  div.id = id;
  div.className = `alert alert-${type}`;
  const closeBtn = document.createElement('button');
  closeBtn.className = 'alert-close';
  closeBtn.textContent = '✕';
  closeBtn.onclick = () => div.remove();
  div.innerHTML = `<span>${message}</span>`;
  div.appendChild(closeBtn);
  area.appendChild(div);
  if(timeout>0){ setTimeout(()=>{ try{ const e=document.getElementById(id); if(e){ e.remove(); } }catch(e){} }, timeout); }
}

async function openEditModal(id){
  const res = await fetch(apiBase + '/nfc/card/' + id);
  if(!res.ok){ showAlert('获取卡片失败','danger'); return; }
  const card = await res.json();
  document.getElementById('editCardId').value = card.id;
  document.getElementById('editCardName').value = card.card_name || '';
  document.getElementById('editIsActive').checked = !!card.is_active;
  document.getElementById('editPermissionEnd').value = card.permission_end_date ? card.permission_end_date.split('T')[0] : '';
  document.getElementById('editMaxDaily').value = card.max_daily_uses || 0;
  document.getElementById('editTimePeriods').value = card.time_periods || '';
  // show modal
  const modal = document.getElementById('editModal');
  modal.classList.add('show');
}

document.addEventListener('click', (e)=>{
  if(e.target && e.target.id === 'saveEdit'){
    (async ()=>{
      const id = document.getElementById('editCardId').value;
      const payload = {
        card_name: document.getElementById('editCardName').value,
        is_active: document.getElementById('editIsActive').checked,
        max_daily_uses: Number(document.getElementById('editMaxDaily').value || 0),
        time_periods: document.getElementById('editTimePeriods').value || null
      };
      const permDate = document.getElementById('editPermissionEnd').value;
      if(permDate) payload.permission_end_date = new Date(permDate).toISOString();
      const r = await fetch(apiBase + '/nfc/card/' + id, {method:'PUT', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload)});
      if(r.ok){
        showAlert('保存成功','success');
        document.getElementById('editModal').classList.remove('show');
        await fetchCards();
      } else {
        showAlert('保存失败','danger');
      }
    })();
  }
});

async function triggerScan(){
  const sel = document.getElementById('deviceSelect');
  const deviceId = sel.value;
  if(!deviceId){
    showAlert('请先选择设备', 'danger');
    return;
  }
  const status = document.getElementById('scanStatus');
  status.textContent = '📡 发送命令中...';
  
  // 创建任务
  const res = await fetch(apiBase + '/nfc/command', {
    method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({device_id:deviceId, command:'SCAN'})
  });
  
  if(!res.ok){
    status.textContent = '❌ 命令发送失败';
    showAlert('无法创建扫描任务', 'danger');
    return;
  }
  
  const task = await res.json();
  status.textContent = `⏳ 等待设备响应... (ID: ${task.id})`;

  // 轮询任务状态
  const start = Date.now();
  const timeout = 20000; // 20s
  while(Date.now() - start < timeout){
    await new Promise(r=>setTimeout(r, 1000));
    const st = await fetch(apiBase + '/nfc/command/status/' + task.id);
    const body = await st.json();
    if(body.status && body.status !== 'pending' && body.status !== 'sent'){
      let display = body.result || body.status;
      // 解析 JSON 结果并美化显示
      try{
        const resObj = JSON.parse(body.result || '{}');
        if(resObj.status === 'success' && resObj.user_id){
          display = `✓ 识别成功：用户 ID ${resObj.user_id}`;
        } else if(resObj.status === 'disabled'){
          display = '✗ 卡片已被禁用';
        } else if(resObj.status === 'expired'){
          display = '✗ 卡片权限已过期';
        } else if(resObj.status){
          display = `✗ ${resObj.status}`;
        }
      }catch(e){ }
      status.textContent = '';
      showResult(display);
      return;
    }
  }
  status.textContent = '⏱️ 超时：设备未返回结果';
}

function showResult(text){
  const card = document.getElementById('resultCard');
  const txt = document.getElementById('resultText');
  txt.textContent = text;
  card.classList.add('show');
}

document.getElementById('closeResult')?.addEventListener('click', ()=>{
  document.getElementById('resultCard').classList.remove('show');
});

// 关闭 modal 时点击外部
document.getElementById('editModal')?.addEventListener('click', (e)=>{
  if(e.target.id === 'editModal'){
    e.target.classList.remove('show');
  }
});

// 绑定事件
window.addEventListener('load', async ()=>{
  document.getElementById('createForm').addEventListener('submit', createCard);
  document.getElementById('btnScan').addEventListener('click', triggerScan);
  document.getElementById('refreshDevices').addEventListener('click', fetchDevices);
  await fetchUsers();
  await fetchDevices();
  await fetchCards();
});

