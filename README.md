# 万千定数：存档格式笔记

游戏本体、补丁和存档留在本机，不进这个仓库。

这是 Eushully 的 AGE 引擎，Steam 应用 3196500，《万千定数孤注破晓之刻》（百千の定にかわたれし剋，EU-022）。磁盘上的 `AGE.EXE` 是加壳的，老的一社改档器（固定密钥 `0xEA83289E`，循环右移 15）对不上这一作。

| 本机位置 | 作用 | 是否入库 |
|---|---|---|
| `steamapps\common\EU22_Wayblazer` | 游戏安装目录 | 否 |
| `%LOCALAPPDATA%\Eushully\EU-022_ZHCN\SAVE` | 存档。`SAVE04.DAT` 是第 5 个手动槽，菜单上写 SAVE 004 | 否 |
| `SAVE04.STH` | 槽位缩略图，是一张位图，游戏自己存档时才重画 | 否 |
| `tools/` | 解密、压缩、改金币和等级 | 是 |

过程写在 [notes/journey.md](notes/journey.md)。字段和算法写在 [notes/format.md](notes/format.md)。

## 改一档

先把要改的 `SAVE0N.DAT` 复制出来。游戏正在读这个文件时不要覆盖它。

```
python tools/edit_slot.py SAVE04.DAT --show
python tools/edit_slot.py SAVE04.DAT --gold 300000 --level 98 -o SAVE04.edited.DAT
```

`--level` 只改等级表的前三项：马克、苏菲亚、瑞理。后面的 0 不动，避免把没入队的角色写出来。经验、装备都不动。

脚本会先核对钱包旁边的 `569, 360, 190`。对不上就停手，不写文件。

满级是 99。40 不是满级，后期有角色入队就是 40。专属武器要到 50 级后去对应地图捡，改等级不会发武器，也不会把身上的装备脱掉。
