"""仪表盘前端页面（内嵌 HTML/CSS/JS，零外部资源）。

通过 EventSource('/events') 订阅 SSE，实时渲染网格世界、任务状态与事件日志。
"""

DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>机器人 Agent 上位机</title>
<style>
  :root { color-scheme: dark; }
  * { box-sizing: border-box; }
  body {
    margin: 0; font-family: -apple-system, "PingFang SC", "Microsoft YaHei", sans-serif;
    background: #0b1220; color: #e5e7eb;
  }
  header { padding: 16px 24px; border-bottom: 1px solid #1f2937; }
  header h1 { margin: 0; font-size: 18px; }
  header .goal { color: #93c5fd; margin-top: 4px; font-size: 14px; }
  main { display: flex; gap: 24px; padding: 24px; flex-wrap: wrap; }
  .panel { background: #111827; border: 1px solid #1f2937; border-radius: 12px; padding: 16px; }
  #grid { display: grid; gap: 4px; }
  .cell {
    width: 34px; height: 34px; border-radius: 6px; background: #1f2937;
    display: flex; align-items: center; justify-content: center;
    font-size: 12px; font-weight: 600; color: #f9fafb;
  }
  .cell.robot { background: #3b82f6; box-shadow: 0 0 0 2px #93c5fd inset; }
  .cell.container { background: #a16207; }
  .cell.cube-red { background: #ef4444; }
  .cell.cube-blue { background: #2563eb; }
  .cell.cube-green { background: #16a34a; }
  .cell.other { background: #4b5563; }
  .status { min-width: 260px; }
  .badge { display: inline-block; padding: 2px 10px; border-radius: 999px; font-size: 13px; }
  .badge.running { background: #1d4ed8; }
  .badge.succeeded { background: #15803d; }
  .badge.failed { background: #b91c1c; }
  .badge.recovering, .badge.pending { background: #a16207; }
  .kv { margin: 8px 0; font-size: 14px; }
  .kv b { color: #9ca3af; font-weight: 500; }
  #log { max-height: 320px; overflow-y: auto; font-size: 13px; line-height: 1.6; }
  #log .ok { color: #86efac; }
  #log .failed { color: #fca5a5; }
  #log .replan { color: #fcd34d; }
  .legend { font-size: 12px; color: #9ca3af; margin-top: 10px; }
  .legend span { display: inline-block; margin-right: 12px; }
  .dot { display: inline-block; width: 10px; height: 10px; border-radius: 3px; margin-right: 4px; vertical-align: middle; }
</style>
</head>
<body>
<header>
  <h1>机器人 Agent Runtime · 上位机监控</h1>
  <div class="goal" id="goal">目标：等待连接…</div>
</header>
<main>
  <section class="panel">
    <div id="grid"></div>
    <div class="legend">
      <span><i class="dot" style="background:#3b82f6"></i>机器人</span>
      <span><i class="dot" style="background:#ef4444"></i>可抓取</span>
      <span><i class="dot" style="background:#a16207"></i>容器</span>
      <span><i class="dot" style="background:#4b5563"></i>其它</span>
    </div>
  </section>
  <section class="panel status">
    <div class="kv"><b>任务状态：</b><span id="status" class="badge pending">-</span></div>
    <div class="kv"><b>当前步骤：</b><span id="step">-</span></div>
    <div class="kv"><b>重规划次数：</b><span id="replans">0</span></div>
    <div class="kv"><b>持有物：</b><span id="holding">（空）</span></div>
    <h3 style="margin:16px 0 8px;font-size:14px;">事件日志</h3>
    <div id="log" class="panel" style="background:#0b1220;"></div>
  </section>
</main>
<script>
  var KIND = {task_started:"任务开始", step_result:"步骤执行", replan:"重规划", task_finished:"任务结束"};
  function cubeClass(color){
    if(color === "red") return "cube-red";
    if(color === "blue") return "cube-blue";
    if(color === "green") return "cube-green";
    return "other";
  }
  function renderGrid(world){
    var grid = document.getElementById("grid");
    grid.style.gridTemplateColumns = "repeat(" + world.width + ", 34px)";
    grid.innerHTML = "";
    var map = {};
    world.objects.forEach(function(o){ map[o.x + "," + o.y] = o; });
    for(var y = 0; y < world.height; y++){
      for(var x = 0; x < world.width; x++){
        var cell = document.createElement("div");
        cell.className = "cell";
        var key = x + "," + y;
        if(world.robot.x === x && world.robot.y === y){
          cell.classList.add("robot"); cell.textContent = "R";
        } else if(map[key]){
          var o = map[key];
          if(o.graspable){ cell.classList.add(cubeClass(o.color)); cell.textContent = "■"; }
          else if(o.container){ cell.classList.add("container"); cell.textContent = "▣"; }
          else { cell.classList.add("other"); }
        }
        grid.appendChild(cell);
      }
    }
  }
  function log(ev){
    var box = document.getElementById("log");
    var line = document.createElement("div");
    var cls = ev.kind === "replan" ? "replan" : (ev.step && ev.step.status === "failed" ? "failed" : "ok");
    var text = KIND[ev.kind] || ev.kind;
    if(ev.step){
      var retry = ev.step.attempt > 0 ? " [重试#" + ev.step.attempt + "]" : "";
      text += "：" + ev.step.skill + retry + " — " + ev.step.message;
    } else if(ev.message){ text += "：" + ev.message; }
    line.className = cls; line.textContent = text;
    box.appendChild(line); box.scrollTop = box.scrollHeight;
  }
  function apply(ev){
    document.getElementById("goal").textContent = "目标：" + (ev.goal || "-");
    renderGrid(ev.world);
    if(ev.task){
      var s = document.getElementById("status");
      s.textContent = ev.task.status + (ev.task.error ? "（" + ev.task.error + "）" : "");
      s.className = "badge " + ev.task.status;
    }
    if(ev.step){
      var retry = ev.step.attempt > 0 ? " [重试#" + ev.step.attempt + "]" : "";
      var icon = ev.step.status === "ok" ? "✅" : "❌";
      document.getElementById("step").textContent = icon + " " + ev.step.skill + retry;
    }
    document.getElementById("replans").textContent = ev.replans;
    document.getElementById("holding").textContent = ev.world.holding || "（空）";
    log(ev);
  }
  var es = new EventSource("/events");
  es.onmessage = function(e){ try { apply(JSON.parse(e.data)); } catch(err){} };
</script>
</body>
</html>
"""
