<script>
  import scraper from "./scrape-links.js?raw" // YouTube link scraper, as text

  const bookmarklet = "javascript:" + encodeURIComponent(scraper)
  // --- state ---
  let urlText = $state("") // URLs typed or loaded from file
  let maxNew = $state(50) // cap on new videos per run (0 = no limit)
  let running = $state(false) // is a fetch job running on the server
  let log = $state([]) // job log lines
  let q = $state("") // search box
  let videos = $state([]) // stored videos (no text)
  let open = $state(null) // video being viewed, with text
  let showFull = $state(false) // viewer: full vs filtered text
  let selected = $state([]) // ids ticked for copying together
  let sortBy = $state("fetched") // list order

  // fetched_at is UTC "2026-11-16 08:15:59" -> local date "2026-11-16"
  const fetchDay = (v) => new Date(v.fetched_at.replace(" ", "T") + "Z").toLocaleDateString("sv")
  const byDate = (a, b) => b.upload_date.localeCompare(a.upload_date)
  const sorters = {
    newest: byDate,
    oldest: (a, b) => -byDate(a, b),
    // newest fetch day first, then by channel, then newest fetch first
    fetched: (a, b) =>
      fetchDay(b).localeCompare(fetchDay(a)) ||
      a.channel.localeCompare(b.channel) ||
      b.fetched_at.localeCompare(a.fetched_at),
    title: (a, b) => a.title.localeCompare(b.title),
    channel: (a, b) => a.channel.localeCompare(b.channel) || byDate(a, b),
    status: (a, b) => a.status.localeCompare(b.status) || byDate(a, b),
  }
  const sorted = $derived([...videos].sort(sorters[sortBy]))

  // "Recently fetched" groups: day, and day|channel. Folded until clicked.
  let expanded = $state({}) // group key -> true when unfolded
  const toggle = (key) => (expanded[key] = !expanded[key])
  const chKey = (v) => fetchDay(v) + "|" + v.channel
  // ids in a group; key is a day ("2026-11-16") or a day|channel
  const groupIds = (key) =>
    videos.filter((v) => fetchDay(v) === key || chKey(v) === key).map((v) => v.id)
  function tickGroup(key, on) {
    const ids = groupIds(key)
    selected = on ? [...new Set([...selected, ...ids])] : selected.filter((id) => !ids.includes(id))
  }
  const counts = $derived.by(() => {
    const c = {}
    for (const v of videos) for (const k of [fetchDay(v), chKey(v)]) c[k] = (c[k] || 0) + 1
    return c
  })

  // export URL: the ticked videos, or everything matching the search if none ticked
  const exportUrl = $derived(
    "/api/export?" +
      (selected.length
        ? `ids=${selected.join(",")}`
        : `q=${encodeURIComponent(q)}`),
  )

  const getJson = async (url) => (await fetch(url)).json()

  async function loadVideos() {
    videos = await getJson(`/api/videos?q=${encodeURIComponent(q)}`)
  }

  // Ask the server for job progress every second while a job runs
  async function poll() {
    const s = await getJson("/api/status")
    if (s.log.length !== log.length) loadVideos() // a video was saved: refresh the list
    running = s.running
    log = s.log
    if (running) setTimeout(poll, 1000)
    else loadVideos()
  }

  async function stopFetch() {
    await fetch("/api/stop", { method: "POST" })
  }

  async function startFetch() {
    const res = await fetch("/api/fetch", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text: urlText, max_new: maxNew || 0 }),
    })
    if (!res.ok) return alert((await res.json()).detail)
    poll()
  }

  async function loadFile(e) {
    urlText = await e.target.files[0].text()
  }

  async function view(id) {
    open = await getJson(`/api/videos/${id}`)
    showFull = false
  }

  async function copy(text) {
    await navigator.clipboard.writeText(text)
    alert(`Copied ${text.length.toLocaleString()} characters`)
  }

  async function copyAll() {
    copy(await (await fetch(exportUrl)).text())
  }

  function toggleAll(e) {
    selected = e.target.checked ? videos.map((v) => v.id) : []
  }

  async function deleteVideos(ids) {
    if (!confirm(`Delete ${ids.length} video(s)? They will be fetched again next run.`)) return
    await fetch(`/api/videos?ids=${ids.join(",")}`, { method: "DELETE" })
    if (open && ids.includes(open.id)) open = null
    selected = selected.filter((id) => !ids.includes(id))
    loadVideos()
  }

  // reusable Tailwind class strings
  const btn =
    "rounded bg-blue-600 px-3 py-1.5 text-sm text-white hover:bg-blue-700 disabled:opacity-50"
  const btnGray =
    "rounded bg-gray-500 px-3 py-1.5 text-sm text-white hover:bg-gray-600"
  const input =
    "rounded border border-gray-300 px-2 py-1.5 text-sm dark:border-gray-600 dark:bg-gray-800"
  const box =
    "whitespace-pre-wrap rounded bg-gray-100 p-3 text-sm max-h-96 overflow-auto dark:bg-gray-800"
  const muted = "text-gray-500 dark:text-gray-400"
  const logColors = {
    info: "",
    ok: "text-green-700 dark:text-green-400",
    warn: "text-amber-700 dark:text-amber-400",
    error: "text-red-600 dark:text-red-400",
  }

  poll() // on page load: show a running job if any, and load the video list
</script>

<main class="mx-auto my-8 max-w-4xl space-y-8 px-4 font-sans">
  <header class="flex flex-wrap items-center gap-3">
    <h1 class="flex-1 text-2xl font-bold">YouTube Transcripts</h1>
    <!-- YouTube link scraper: copy for the console, or drag the link to the bookmarks bar -->
    <button class={btnGray} onclick={() => copy(scraper)}>Copy link scraper</button>
    <a
      class="text-sm text-blue-600 hover:underline dark:text-blue-400"
      href={bookmarklet}
      title="Drag to your bookmarks bar"
      onclick={(e) => e.preventDefault()}>YT links ⇲</a
    >
  </header>

  <section class="space-y-2">
    <textarea
      class="{input} w-full"
      rows="5"
      bind:value={urlText}
      placeholder="Channel / playlist / video URLs, one per line"></textarea>
    <div class="flex flex-wrap items-center gap-3">
      <input
        type="file"
        accept=".txt,.csv"
        class="text-sm"
        onchange={loadFile}
      />
      <label class="text-sm"
        >Max new videos
        <input
          type="number"
          min="0"
          class="{input} ml-1 w-20"
          bind:value={maxNew}
        />
      </label>
      <button class={btn} onclick={startFetch} disabled={running}
        >{running ? "Running…" : "Fetch"}</button
      >
      {#if running}
        <button class={btnGray} onclick={stopFetch}>Stop</button>
      {/if}
    </div>
    {#if log.length}
      <pre class={box}>{#each log as l}<div class={logColors[l.level]}>{new Date(l.time * 1000).toLocaleTimeString("sv")}  {l.msg}</div>{/each}</pre>
    {/if}
  </section>

  <section class="space-y-2">
    <div class="flex flex-wrap items-center gap-3">
      <input
        type="checkbox"
        title="Select all"
        checked={videos.length > 0 && selected.length === videos.length}
        onchange={toggleAll}
      />
      <input
        class="{input} flex-1"
        placeholder="Search title or channel"
        bind:value={q}
        oninput={loadVideos}
      />
      <select class={input} bind:value={sortBy}>
        <option value="newest">Newest</option>
        <option value="oldest">Oldest</option>
        <option value="fetched">Recently fetched</option>
        <option value="title">Title</option>
        <option value="channel">Channel</option>
        <option value="status">Status</option>
      </select>
      <button class={btn} onclick={copyAll}
        >{selected.length ? `Copy ${selected.length} selected` : "Copy all filtered"}</button
      >
      <a
        class="text-sm text-blue-600 hover:underline dark:text-blue-400"
        href={`${exportUrl}&download=true`}>Download</a
      >
      {#if selected.length}
        <button class="{btn} bg-red-600 hover:bg-red-700" onclick={() => deleteVideos(selected)}
          >Delete</button
        >
      {/if}
      <span class="text-sm {muted}">{videos.length} videos</span>
    </div>
    <ul class="divide-y divide-gray-200 dark:divide-gray-700">
      {#each sorted as v, i (v.id)}
        {@const grouped = sortBy === "fetched"}
        {@const day = fetchDay(v)}
        {@const ch = chKey(v)}
        {@const prev = sorted[i - 1]}
        {#if grouped && (!prev || fetchDay(prev) !== day)}
          <li class="pt-4 pb-1">
            <input
              type="checkbox"
              class="mr-2"
              checked={groupIds(day).every((id) => selected.includes(id))}
              onchange={(e) => tickGroup(day, e.target.checked)}
            />
            <button class="text-sm font-semibold {muted}" onclick={() => toggle(day)}
              >{expanded[day] ? "▾" : "▸"} Fetched {day} ({counts[day]})</button
            >
          </li>
        {/if}
        {#if grouped && expanded[day] && (!prev || chKey(prev) !== ch)}
          <li class="pt-2 pl-4">
            <input
              type="checkbox"
              class="mr-2"
              checked={groupIds(ch).every((id) => selected.includes(id))}
              onchange={(e) => tickGroup(ch, e.target.checked)}
            />
            <button class="text-sm font-medium" onclick={() => toggle(ch)}
              >{expanded[ch] ? "▾" : "▸"} {v.channel || "(unknown channel)"} ({counts[ch]})</button
            >
          </li>
        {/if}
        {#if !grouped || (expanded[day] && expanded[ch])}
        <li class="py-1.5 {grouped ? 'pl-8' : ''}">
          <input
            type="checkbox"
            class="mr-2"
            value={v.id}
            bind:group={selected}
          />
          <button
            class="text-left text-blue-700 hover:underline disabled:text-gray-400 disabled:no-underline dark:text-blue-400 dark:disabled:text-gray-500"
            onclick={() => view(v.id)}
            disabled={v.status !== "ok"}>{v.title}</button
          >
          <small class="ml-2 {muted}"
            >{v.upload_date} · {v.channel} · {v.status}</small
          >
        </li>
        {/if}
      {/each}
    </ul>
  </section>

  {#if open}
    <section class="space-y-2">
      <div class="flex flex-wrap items-center gap-3">
        <strong class="flex-1">{open.title}</strong>
        <label class="text-sm"
          ><input type="checkbox" bind:checked={showFull} /> Full text</label
        >
        <button
          class={btn}
          onclick={() => copy(showFull ? open.full_text : open.filtered_text)}
          >Copy</button
        >
        <button class="{btn} bg-red-600 hover:bg-red-700" onclick={() => deleteVideos([open.id])}
          >Delete</button
        >
        <button class={btnGray} onclick={() => (open = null)}>Close</button>
      </div>
      <pre class={box}>{showFull ? open.full_text : open.filtered_text}</pre>
    </section>
  {/if}
</main>
