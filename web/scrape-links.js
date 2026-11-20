// YouTube link scraper (not part of the app; the app offers it as a copy button and a bookmarklet).
// Use on a channel's Videos page, in any sort order (e.g. Popular): paste into the browser
// console (F12), or click the bookmarklet with the console open. Prints watch URLs, one per line.
(async () => {
  const answer = prompt("How many links? (0 = all)", "50")
  if (answer === null || Number.isNaN(Number(answer))) return
  const limit = Number(answer)
  const page = document.querySelector("ytd-browse:not([hidden])") // visible page only, not old hidden ones
  if (!page) return alert("Open a channel's Videos page first")
  const ids = () => [
    ...new Set(
      [...page.querySelectorAll('a[href*="/watch?v="]')].map((a) => new URL(a.href).searchParams.get("v")),
    ),
  ]
  let height = 0
  while (!limit || ids().length < limit) {
    window.scrollTo(0, document.documentElement.scrollHeight) // load more videos
    await new Promise((r) => setTimeout(r, 1500))
    if (document.documentElement.scrollHeight === height) break // reached the end
    height = document.documentElement.scrollHeight
  }
  const urls = ids()
    .slice(0, limit || undefined)
    .map((id) => `https://www.youtube.com/watch?v=${id}`)
  console.log(urls.join("\n"))
})()
