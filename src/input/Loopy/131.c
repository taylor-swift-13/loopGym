// Source: data/benchmarks/LinearArbitrary-SeaHorn/pie/hola/20.c

extern int unknown1();

/*@
  requires (x + y) == k;
*/
void loopy_131(int x, int y, int k, int j, int i, int n)
{
    if((x+y)== k) {
    int m = 0;
    j = 0;
    while(j<n) {
      if(j==i)
      {
         x++;
         y--;
      }else
      {
         y++;
         x--;
      }
	if(unknown1())
  		m = j;
      j++;
    }
    {;
//@ assert((x+y)== k);
}

    if(n>0)
    {
   	{;
//@ assert(0<=m);
}
 
	{;
//@ assert(m<n);
}

    }
    }
}
