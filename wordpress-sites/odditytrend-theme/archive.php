<?php
/**
 * Category / tag / date archive template.
 */
if ( ! defined( 'ABSPATH' ) ) {
	exit;
}
get_header();
?>
<header class="archive-header">
	<h1><?php the_archive_title(); ?></h1>
	<?php the_archive_description( '<div class="archive-description">', '</div>' ); ?>
</header>

<div class="content-layout">
	<div>
		<?php if ( have_posts() ) : ?>
			<div class="post-grid">
				<?php
				while ( have_posts() ) :
					the_post();
					get_template_part( 'template-parts/content' );
				endwhile;
				?>
			</div>
			<?php ot_pagination(); ?>
		<?php else : ?>
			<?php get_template_part( 'template-parts/content', 'none' ); ?>
		<?php endif; ?>
	</div>
	<?php get_sidebar(); ?>
</div>
<?php get_footer(); ?>
