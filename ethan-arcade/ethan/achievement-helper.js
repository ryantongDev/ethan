window.EthanAchievements = {
  check() {
    const got = JSON.parse(localStorage.getItem('ethan_arcade_achievement_seen') || '[]');
    const add = [];
    const target = Number(localStorage.getItem('ethan-target-best') || 0);
    const balloon = Number(localStorage.getItem('ethan-balloon-best') || 0);
    const dodge = Number(localStorage.getItem('ethan-dodge-best') || 0);
    const relax = Number(localStorage.getItem('ethan-relax-best') || 0);
    const counter = Number(localStorage.getItem('simple-counter-value') || 0);
    const rules = [
      ['target50','🎯 解锁成就：新手射手', target >= 50],
      ['target150','🏹 解锁成就：神射手', target >= 150],
      ['balloon60','🎈 解锁成就：气球杀手', balloon >= 60],
      ['dodge15','🌀 解锁成就：生存者', dodge >= 15],
      ['relax30','🫧 解锁成就：解压学徒', relax >= 30],
      ['counter100','🔢 解锁成就：数字狂人', counter >= 100],
    ];
    for (const [id, text, ok] of rules) {
      if (ok && !got.includes(id)) add.push([id, text]);
    }
    if (add.length) {
      localStorage.setItem('ethan_arcade_achievement_seen', JSON.stringify(got.concat(add.map(x => x[0]))));
    }
    return add.map(x => x[1]);
  },
  toast(text) {
    const el = document.createElement('div');
    el.textContent = text;
    Object.assign(el.style, {
      position:'fixed', top:'20px', left:'50%', transform:'translateX(-50%)', zIndex:'9999',
      background:'rgba(17,24,39,.92)', color:'#fff', padding:'12px 16px', borderRadius:'14px',
      border:'1px solid rgba(255,255,255,.15)', boxShadow:'0 10px 24px rgba(0,0,0,.25)', fontWeight:'700'
    });
    document.body.appendChild(el);
    setTimeout(() => el.remove(), 2600);
  },
  run() {
    const list = this.check();
    list.forEach((text, i) => setTimeout(() => this.toast(text), i * 900));
  }
};
