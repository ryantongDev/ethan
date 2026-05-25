(function(){
  var LANG_KEY='ethan-arcade-lang';
  var lang=localStorage.getItem(LANG_KEY)||'zh';
  var langData={
    zh:{
      // Hall page
      title:'Ethan 小游戏站',
      tag:'ETHAN ARCADE',
      welcome:'欢迎回来，%s 👋',
      desc:'这里是独立挂在 <b>/ethan/</b> 下的小型游戏站，和主项目隔离。现在已经能玩射击、射靶、弹弓、躲避、打架、解压、切西瓜、打地鼠和 Geometry Dash 这些小游戏，还加了解释音效、背景音乐和众多游戏功能。',
      gameCount:'🎮 游戏数量：%s',
      soundOn:'🔊 音效：已开启',
      music:'🎵 背景音乐：可开关',
      achSection:'成就树与皮肤系统',
      achDesc:'现在已经有统一的成就树、徽章大厅和皮肤解锁展示页。首页会根据你已解锁的主题自动切换风格。',
      badgeScore:'本地成绩已启用',
      badgeIsolation:'主项目隔离',
      badgeMobile:'支持手机访问',
      enter:'进入游戏 →',
      enterPage:'进入页面 →',
      enterTrain:'进入训练 →',
      enterDuel:'进入对枪 →',
      authTitle:'Ethan 小游戏站 - 登录',
      authDesc:'输入你的用户名开始玩', 
      authBtn:'进入游戏站',
      authPlaceholder:'输入用户名',

      // Card titles and descriptions
      cardAch:'成就与排行榜',
      cardAchDesc:'查看本地成绩、解锁成就和当前战绩。',
      cardShoot:'射击小游戏',
      cardShootDesc:'横向移动，持续开火，清掉敌人。',
      cardTarget:'射靶小游戏',
      cardTargetDesc:'点中靶心，分数更高，考验手感。',
      cardBalloon:'弹弓打气球',
      cardBalloonDesc:'拉弹弓、打气球，节奏轻松。',
      cardDodge:'躲避小游戏',
      cardDodgeDesc:'拖动角色，避开陨石，坚持更久。',
      cardDash:'Geometry Dash',
      cardDashDesc:'几何冲刺，跳过障碍物，越跑越快。',
      cardFight:'打架小游戏',
      cardFightDesc:'靠近对手，挥拳对打，先击倒先赢。',
      cardRelax:'解压小游戏',
      cardRelaxDesc:'疯狂点泡泡，轻松解压。',
      cardCounter:'计数器',
      cardCounterDesc:'一个简单的小工具，也算站内功能页。',
      cardCSRange:'CS 风格打靶',
      cardCSRangeDesc:'练枪模式，打身体得分，爆头更高分。',
      cardCSDuel:'CS 风格轻量对枪',
      cardCSDuelDesc:'你 vs 敌人，轻量对枪回合制，掩体会挡枪。',
      cardFruit:'切西瓜',
      cardFruitDesc:'滑动切水果，时间内尽量多切。',
      cardMole:'打地鼠',
      cardMoleDesc:'地鼠冒头就打，拼手速。',
      langBtn:'EN',

      // Theme names
      themeDefault:'ETHAN ARCADE',
      themeHunter:'蓝色猎手主题',
      themeCandy:'糖果气球主题',
      themeSpace:'深空逃生主题',
      themeBubble:'清凉泡泡主题',
      themeFruit:'水果狂欢主题',
      themeMole:'嘉年华地鼠主题',
      themeTactical:'战术靶场主题',
      themeDuel:'对枪战场主题',
    },
    en:{
      title:'Ethan Arcade',
      tag:'ETHAN ARCADE',
      welcome:'Welcome back, %s 👋',
      desc:'A small game site under <b>/ethan/</b>, isolated from the main project. Play shooting, target practice, slingshot balloons, dodge, fight, chill, fruit ninja, whack-a-mole, and Geometry Dash games, with sound effects, background music, and achievement systems.',
      gameCount:'🎮 Games: %s',
      soundOn:'🔊 Sound: On',
      music:'🎵 Music: Toggle',
      achSection:'Achievements & Skins',
      achDesc:'Unified achievement tree, badge hall, and skin unlocking showcase. The home page auto-switches themes based on your unlocked skins.',
      badgeScore:'Local scores enabled',
      badgeIsolation:'Isolated from main project',
      badgeMobile:'Mobile friendly',
      enter:'Play →',
      enterPage:'View →',
      enterTrain:'Train →',
      enterDuel:'Duel →',
      authTitle:'Ethan Arcade - Login',
      authDesc:'Enter your username to start playing',
      authBtn:'Enter Arcade',
      authPlaceholder:'Enter username',

      cardAch:'Achievements & Ranking',
      cardAchDesc:'View local scores, unlock achievements and check stats.',
      cardShoot:'Shooting Game',
      cardShootDesc:'Move sideways, keep firing, clear enemies.',
      cardTarget:'Target Practice',
      cardTargetDesc:'Click the bullseye for higher scores.',
      cardBalloon:'Slingshot Balloons',
      cardBalloonDesc:'Pull and shoot balloons at a relaxed pace.',
      cardDodge:'Dodge Game',
      cardDodgeDesc:'Drag to dodge meteors, survive as long as possible.',
      cardDash:'Geometry Dash',
      cardDashDesc:'Jump over obstacles and go faster and faster.',
      cardFight:'Fighting Game',
      cardFightDesc:'Get close, throw punches, knock them out first.',
      cardRelax:'Relax Game',
      cardRelaxDesc:'Tap bubbles frantically to relax.',
      cardCounter:'Counter',
      cardCounterDesc:'A simple tool, also a site utility page.',
      cardCSRange:'CS-Style Range',
      cardCSRangeDesc:'Shoot body for points, headshot for bonus.',
      cardCSDuel:'CS-Style Duel',
      cardCSDuelDesc:'You vs enemy, turn-based duel with cover mechanics.',
      cardFruit:'Fruit Ninja',
      cardFruitDesc:'Swipe to slice fruit, cut as many as you can.',
      cardMole:'Whack-a-Mole',
      cardMoleDesc:'Whack the moles as they pop up.',
      langBtn:'中',

      themeDefault:'ETHAN ARCADE',
      themeHunter:'Blue Hunter Theme',
      themeCandy:'Candy Balloon Theme',
      themeSpace:'Deep Space Theme',
      themeBubble:'Cool Bubble Theme',
      themeFruit:'Fruit Carnival Theme',
      themeMole:'Carnival Mole Theme',
      themeTactical:'Tactical Range Theme',
      themeDuel:'Duel Battlefield Theme',
    }
  };
  window.lang=lang;
  window.langData=langData;
  window.tr=function(key){
    var d=langData[lang];
    var val=d[key];
    if(val===undefined)val=langData['zh'][key]||key;
    return val;
  };
  window.setLang=function(l){
    lang=l;
    localStorage.setItem(LANG_KEY,l);
    window.lang=lang;
    document.documentElement.lang=lang==='zh'?'zh-CN':'en';
    // update all data-i18n elements
    document.querySelectorAll('[data-i18n]').forEach(function(el){
      el.innerHTML=tr(el.getAttribute('data-i18n'));
    });
    document.querySelectorAll('[data-i18n-ph]').forEach(function(el){
      el.innerHTML=tr(el.getAttribute('data-i18n-ph'));
    });
    // update lang button
    var langBtn=document.getElementById('langBtn');
    if(langBtn)langBtn.textContent=tr('langBtn');
  };
  window.toggleLang=function(){
    setLang(lang==='zh'?'en':'zh');
  };
  // Apply lang on load
  setLang(lang);
  window.addEventListener('DOMContentLoaded',function(){
    document.querySelectorAll('[data-i18n]').forEach(function(el){
      el.innerHTML=tr(el.getAttribute('data-i18n'));
    });
    var langBtn=document.getElementById('langBtn');
    if(langBtn)langBtn.textContent=tr('langBtn');
  });
})();
