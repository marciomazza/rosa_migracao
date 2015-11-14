/* tabelas ordenadas por data de criacao - só funciona no servidor original, via phpmyadmin */
SELECT table_name, create_time, update_time, check_time FROM `information_schema`.`tables` WHERE `table_schema` = 'rosadavida1' ORDER BY `tables`.`CREATE_TIME`  ASC

/* tabelas relevantes ordenadas por qtd de linhas */
SELECT TABLE_NAME, TABLE_ROWS FROM `information_schema`.`tables`
WHERE `table_schema` = 'rosa'
and table_name like 'j25_%'
order by TABLE_ROWS desc;

/* nada - todas as mensagens são do mesmo tipo */
select message from j25_messages
where message not like 'Um novo artigo foi enviado por %';

/* nada - não há redirects */
SELECT distinct new_url
FROM `j25_redirect_links`

/* nada - todos os arquivos estao na mesma pasta */
SELECT * FROM j25_attachments
where filename_sys not like '/home/storage/9/33/21%'

/* conteudo com categoria */
/* see http://stackoverflow.com/questions/11887160/how-to-detect-unpublished-content-in-joomla-db */
SELECT c.id, c.title, c.alias, a.name, a.title, a.introtext description, a.fulltext text, a.catid,
  a.created, a.created_by, a.modified, a.hits,
  p.name, p.title FROM j25_content c, j25_assets a, j25_assets p
where c.asset_id = a.id
and a.parent_id = p.id
and state <> -2 -- exclude marked for deletion

/* ASSETS: hierarquia
 vide:
 https://docs.joomla.org/Fixing_the_assets_table */
SELECT * from j25_assets
where id in (608, 39, 35, 8, 1)

/* filtrar por published = 1,
  vide:
  http://stackoverflow.com/questions/11887160/how-to-detect-unpublished-content-in-joomla-db */

/* routing: */
/* https://docs.joomla.org/Search_Engine_Friendly_URLs */


/* ASSETS: contagem de filhos */
SELECT p.id, p.name, p.title, count(f.id), min(f.id) from j25_assets p, j25_assets f
where p.id = f.parent_id
group by p.id

SELECT * from j25_assets
where parent_id = 35



/* OUTROS */
/* maria damiao */
select * from j25_menu
where published = 1
-- and link not like 'index.php?option=com_content&view=article&id=%'
and link like '%662%'

/* users */
select name, username, email, registerDate from j25_users






