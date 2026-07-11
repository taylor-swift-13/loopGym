// Source: data/benchmarks/accelerating_invariant_generation/dagger/seesaw.c
extern int unknown_int(void);

int nondet_int();

/*@
  requires x==0;
  requires y==0;
*/
void loopy_184(int x, int y)
{
	
	

	

	

	while (unknown_int())
	{
		if (unknown_int())
		{
			if (! (x >= 9)) 
return;

			x = x + 2;
			y = y + 1;
		}
		else
		{
			if (unknown_int())
			{
				if (!(x >= 7)) 
return;

				if (!(x <= 9)) 
return;

				x = x + 1;
				y = y + 3;
			}
			else
			{
				if (unknown_int())
				{
					if (! (x - 5 >=0)) 
return;

					if (! (x - 7 <=0)) 
return;

					x = x + 2;
					y = y + 1;
				}
				else
				{
					if (!(x - 4 <=0)) 
return;

					x = x + 1;
					y = y + 2;
				}
			}
		}
	}
	{;
//@ assert(-x + 2*y  >= 0);
}

	{;
//@ assert(3*x - y  >= 0);
}

}
