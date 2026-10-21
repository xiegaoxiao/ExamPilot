import { test, expect } from "@playwright/test";

test("human approval, separate publication, practice and pending-fill review", async ({
  page,
  request,
}) => {
  const response = await request.get("/api/subjects");
  const subjects = await response.json();
  const subject = subjects.find(
    (s: { name: string }) => s.name === "软件需求工程",
  );
  expect(subject).toBeTruthy();
  await page.goto("/review");
  await expect(
    page.getByRole("heading", { name: "审核中心", exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "选择全部待审题" }).click();
  await page.getByRole("button", { name: /批准所选/ }).click();
  await page.getByRole("button", { name: "确认批准", exact: true }).click();
  await expect(page.getByText("批量批准成功", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "选择全部已批准题" }).click();
  await page.getByRole("button", { name: /发布所选/ }).click();
  await page.getByRole("button", { name: "确认发布", exact: true }).click();
  await expect(page.getByText("发布成功", { exact: true })).toBeVisible();
  await page.goto("/practice?kind=fill");
  await page.getByRole("button", { name: "开始练习", exact: true }).click();
  await page.getByPlaceholder("请输入你的答案").fill("这是一个需要复核的答案");
  await page.getByRole("button", { name: "提交答案", exact: true }).click();
  await expect(page.getByText("待人工复核", { exact: true })).toBeVisible();
  await page.goto("/mistakes?view=pending");
  await expect(
    page.getByText("这是一个需要复核的答案", { exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "确认错误", exact: true })
    .first()
    .click();
  await page.getByRole("button", { name: "确认复核", exact: true }).click();
  await expect(page.getByText("复核已记录", { exact: true })).toBeVisible();
  await page.goto("/mistakes?view=history");
  await expect(
    page.getByText("这是一个需要复核的答案", { exact: true }),
  ).toBeVisible();
});

test("course creation, chapter creation, PDF upload and responsive navigation", async ({
  page,
  request,
}) => {
  await page.goto("/courses");
  await page.getByRole("button", { name: "新建课程", exact: true }).click();
  await page.getByLabel("课程名称").fill("浏览器验收课程");
  await page.getByRole("button", { name: "保存课程", exact: true }).click();
  await page.getByRole("link", { name: /浏览器验收课程/ }).click();
  await page.getByRole("button", { name: "添加章节", exact: true }).click();
  await page.getByLabel("章节名称").fill("第一章 浏览器验收");
  await page.getByRole("button", { name: "保存章节", exact: true }).click();
  await expect(
    page.getByText("第一章 浏览器验收", { exact: true }),
  ).toBeVisible();
  const subjects = await (await request.get("/api/subjects")).json();
  const sample = subjects.find(
    (s: { name: string }) => s.name === "软件需求工程",
  );
  const sources = await (
    await request.get(`/api/subjects/${sample.id}/sources`)
  ).json();
  const pdf = await request.get(
    `/api/subjects/${sample.id}/sources/${sources[0].id}/file`,
  );
  await page.getByRole("button", { name: "教材资料", exact: true }).click();
  await page.locator('input[type="file"]').setInputFiles({
    name: "原创教材.pdf",
    mimeType: "application/pdf",
    buffer: await pdf.body(),
  });
  await expect(page.getByText("原创教材.pdf", { exact: true })).toBeVisible();
  await page.setViewportSize({ width: 390, height: 844 });
  await page.getByRole("button", { name: "打开导航" }).click();
  await expect(
    page.getByRole("link", { name: "每日复习", exact: true }),
  ).toBeVisible();
});

for (const kind of ["single", "multiple", "boolean", "fill"]) {
  test(`browser correctly submits ${kind} answers`, async ({
    page,
    request,
  }) => {
    const subjects = await (await request.get("/api/subjects")).json();
    const subject = subjects.find(
      (s: { name: string }) => s.name === "软件需求工程",
    );
    const qs = await (
      await request.get(`/api/subjects/${subject.id}/questions?kind=${kind}`)
    ).json();
    const q = qs.find((q: { active: boolean }) => q.active);
    await page.goto(`/practice?subject=${subject.id}&version=${q.id}`);
    await page.getByRole("button", { name: "开始练习", exact: true }).click();
    if (kind === "fill")
      await page.getByPlaceholder("请输入你的答案").fill(q.answer[0]);
    else if (kind === "multiple")
      for (const value of q.answer)
        await page.locator(`input[value="${value}"]`).check();
    else await page.locator(`input[value="${String(q.answer)}"]`).check();
    await page.getByRole("button", { name: "提交答案", exact: true }).click();
    await expect(page.getByText("回答正确", { exact: true })).toBeVisible();
    await page.getByRole("button", { name: "完成本轮", exact: true }).click();
    await expect(
      page.getByRole("heading", { name: "一次专注，已经完成" }),
    ).toBeVisible();
  });
}

test("all main pages render without runtime errors or mobile overflow", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  for (const width of [1440, 390]) {
    await page.setViewportSize({ width, height: 900 });
    for (const path of [
      "/",
      "/courses",
      "/questions",
      "/practice",
      "/mistakes",
      "/plans",
      "/review",
      "/settings",
    ]) {
      await page.goto(path);
      await expect(page.locator("main h1")).toBeVisible();
      await expect(
        page.getByText("正在连接你的学习空间…", { exact: true }),
      ).toHaveCount(0);
      expect(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= window.innerWidth,
        ),
      ).toBe(true);
    }
  }
  expect(errors).toEqual([]);
});

test("external network blocked: plan generation and manual deferral still work", async ({
  page,
}) => {
  const external: string[] = [];
  await page.route("**/*", (route) => {
    const url = new URL(route.request().url());
    if (["127.0.0.1", "localhost"].includes(url.hostname))
      return route.continue();
    external.push(url.href);
    return route.abort();
  });
  await page.goto("/plans");
  await page.getByRole("button", { name: "重新规划今日", exact: true }).click();
  await page.getByRole("button", { name: "确认重新规划", exact: true }).click();
  await expect(
    page.getByText("今日计划已重新规划", { exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "延期", exact: true }).first().click();
  await page.getByRole("button", { name: "保存延期", exact: true }).click();
  await expect(page.getByText("计划调整已保存", { exact: true })).toBeVisible();
  await page.reload();
  await expect(
    page.getByRole("button", { name: "恢复到今日", exact: true }).first(),
  ).toBeVisible();
  expect(external).toEqual([]);
});
